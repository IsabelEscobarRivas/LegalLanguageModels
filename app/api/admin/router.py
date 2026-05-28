"""Restricted admin purge endpoints with permanent audit logging."""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import TokenClaims, get_current_claims
from app.core.database import get_db
from app.core.models import (
    AdminPurgeLog,
    Case,
    Chunk,
    ClassificationResult,
    Document,
    DocumentVersion,
    Embedding,
    GenerationTrace,
    KBChunk,
    KBDocument,
    KBEmbedding,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class PurgeRequest(BaseModel):
    confirmation: str
    reason: str


def require_admin_role(
    claims: TokenClaims = Depends(get_current_claims),
) -> TokenClaims:
    if claims.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return claims


def _expected_confirmation(target_id: str) -> str:
    return f"CONFIRM_PURGE_{target_id[:8].upper()}"


@router.post("/purge/document/{document_id}")
def purge_document(
    *,
    document_id: str,
    body: PurgeRequest,
    claims: TokenClaims = Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    if body.confirmation != _expected_confirmation(document_id):
        raise HTTPException(status_code=422, detail="Invalid confirmation token")

    document = (
        db.query(Document)
        .join(Case, Case.id == Document.case_id)
        .filter(Document.id == document_id, Case.firm_id == claims.firm_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    trace_count = (
        db.query(GenerationTrace)
        .join(Chunk, Chunk.id == GenerationTrace.chunk_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .filter(DocumentVersion.document_id == document_id)
        .count()
    )
    if trace_count > 0:
        raise HTTPException(
            status_code=409,
            detail="Document has generation traces — use archival not purge",
        )

    version_ids = [
        version.id
        for version in db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .all()
    ]
    chunk_ids = [
        chunk.id
        for chunk in db.query(Chunk)
        .filter(Chunk.document_version_id.in_(version_ids))
        .all()
    ]

    embeddings_deleted = 0
    classifications_deleted = 0
    chunks_deleted = 0

    if chunk_ids:
        embeddings_deleted = (
            db.query(Embedding)
            .filter(Embedding.chunk_id.in_(chunk_ids))
            .delete(synchronize_session=False)
        )
        classifications_deleted = (
            db.query(ClassificationResult)
            .filter(ClassificationResult.chunk_id.in_(chunk_ids))
            .delete(synchronize_session=False)
        )
        chunks_deleted = (
            db.query(Chunk)
            .filter(Chunk.id.in_(chunk_ids))
            .delete(synchronize_session=False)
        )

    document.lifecycle_state = "purged"
    document.retrieval_eligible = False
    document.generation_eligible = False
    document.updated_at = datetime.utcnow()

    purge_id = str(uuid.uuid4())
    log_row = AdminPurgeLog(
        id=purge_id,
        actor_id=claims.sub,
        firm_id=claims.firm_id,
        target_type="document",
        target_id=document_id,
        action="hard_delete",
        detail={
            "reason": body.reason,
            "chunks_deleted": chunks_deleted,
            "embeddings_deleted": embeddings_deleted,
            "classifications_deleted": classifications_deleted,
        },
    )
    db.add(log_row)
    db.commit()

    return {
        "purge_id": purge_id,
        "document_id": document_id,
        "chunks_deleted": chunks_deleted,
        "embeddings_deleted": embeddings_deleted,
    }


@router.post("/purge/kb-document/{kb_document_id}")
def purge_kb_document(
    *,
    kb_document_id: str,
    body: PurgeRequest,
    claims: TokenClaims = Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    if body.confirmation != _expected_confirmation(kb_document_id):
        raise HTTPException(status_code=422, detail="Invalid confirmation token")

    kb_document = (
        db.query(KBDocument)
        .filter(
            KBDocument.id == kb_document_id,
            KBDocument.firm_id == claims.firm_id,
        )
        .first()
    )
    if kb_document is None:
        raise HTTPException(status_code=404, detail="KB document not found")

    chunk_ids = [
        chunk.id
        for chunk in db.query(KBChunk)
        .filter(KBChunk.kb_document_id == kb_document_id)
        .all()
    ]

    embeddings_deleted = 0
    chunks_deleted = 0

    if chunk_ids:
        embeddings_deleted = (
            db.query(KBEmbedding)
            .filter(KBEmbedding.kb_chunk_id.in_(chunk_ids))
            .delete(synchronize_session=False)
        )
        chunks_deleted = (
            db.query(KBChunk)
            .filter(KBChunk.id.in_(chunk_ids))
            .delete(synchronize_session=False)
        )

    kb_document.lifecycle_state = "purged"
    kb_document.updated_at = datetime.utcnow()

    purge_id = str(uuid.uuid4())
    log_row = AdminPurgeLog(
        id=purge_id,
        actor_id=claims.sub,
        firm_id=claims.firm_id,
        target_type="kb_document",
        target_id=kb_document_id,
        action="hard_delete",
        detail={
            "reason": body.reason,
            "chunks_deleted": chunks_deleted,
            "embeddings_deleted": embeddings_deleted,
        },
    )
    db.add(log_row)
    db.commit()

    return {
        "purge_id": purge_id,
        "kb_document_id": kb_document_id,
        "chunks_deleted": chunks_deleted,
        "embeddings_deleted": embeddings_deleted,
    }


@router.get("/purge/log")
def get_purge_log(
    *,
    claims: TokenClaims = Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AdminPurgeLog)
        .filter(AdminPurgeLog.firm_id == claims.firm_id)
        .order_by(AdminPurgeLog.created_at.desc())
        .all()
    )

    return {
        "firm_id": claims.firm_id,
        "entries": [
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "firm_id": row.firm_id,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "action": row.action,
                "detail": row.detail,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }
