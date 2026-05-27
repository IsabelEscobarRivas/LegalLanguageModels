"""Knowledge base endpoints — firm-scoped institutional memory."""
import logging
import os
import uuid
from typing import Literal

import boto3
import openai
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.auth import TokenClaims, get_current_claims
from app.core.database import get_db
from app.core.models import KBChunk, KBDocument, KBEmbedding
from app.ingestion.embedder import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL


logger = logging.getLogger(__name__)

router = APIRouter(tags=["kb"])

AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")


class KBSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1)


def _s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def _bucket() -> str:
    bucket = os.environ.get("S3_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME is not configured")
    return bucket


def _upload_kb_file(
    file_bytes: bytes,
    s3_key: str,
    content_type: str | None = None,
) -> str:
    extra: dict = {}
    if content_type:
        extra["ContentType"] = content_type
    _s3_client().put_object(
        Bucket=_bucket(),
        Key=s3_key,
        Body=file_bytes,
        **extra,
    )
    return s3_key


def _embed_query(query: str) -> list[float]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Query embedding failed")
    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(
        input=query,
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


def _get_kb_document(
    db: Session,
    kb_document_id: str,
    firm_id: str,
) -> KBDocument | None:
    return (
        db.query(KBDocument)
        .filter(
            KBDocument.id == kb_document_id,
            KBDocument.firm_id == firm_id,
        )
        .first()
    )


@router.post("/kb/documents", status_code=201)
async def upload_kb_document(
    *,
    title: str = Form(...),
    document_type: Literal["style_guide", "firm_convention", "precedent_letter"] = Form(
        ...
    ),
    file: UploadFile = File(...),
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Upload a KB document for the authenticated firm."""
    kb_document_id = str(uuid.uuid4())
    original_filename = file.filename or "untitled"
    s3_key = (
        f"kb/{claims.firm_id}/{document_type}/{kb_document_id}/{original_filename}"
    )

    file_bytes = await file.read()
    try:
        _upload_kb_file(file_bytes, s3_key, content_type=file.content_type)
    except Exception:
        logger.exception("KB document S3 upload failed for firm %s", claims.firm_id)
        raise HTTPException(status_code=503, detail="KB document upload failed")

    kb_document = KBDocument(
        id=kb_document_id,
        firm_id=claims.firm_id,
        title=title,
        document_type=document_type,
        s3_key=s3_key,
        lifecycle_state="uploaded",
    )
    db.add(kb_document)
    db.commit()
    db.refresh(kb_document)

    # ProcessingEvent.case_id is NOT NULL — KB uploads are not case-scoped,
    # so event write is skipped until schema supports nullable case_id.

    return {
        "kb_document_id": kb_document.id,
        "firm_id": kb_document.firm_id,
        "title": kb_document.title,
        "document_type": kb_document.document_type,
        "s3_key": kb_document.s3_key,
        "lifecycle_state": kb_document.lifecycle_state,
    }


@router.get("/kb/documents")
def list_kb_documents(
    *,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """List KB documents for the authenticated firm."""
    rows = (
        db.query(KBDocument)
        .filter(KBDocument.firm_id == claims.firm_id)
        .order_by(KBDocument.created_at.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "document_type": row.document_type,
            "lifecycle_state": row.lifecycle_state,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/kb/documents/{kb_document_id}")
def get_kb_document(
    *,
    kb_document_id: str,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Retrieve a single KB document with chunk count."""
    kb_document = _get_kb_document(db, kb_document_id, claims.firm_id)
    if kb_document is None:
        raise HTTPException(status_code=404, detail="KB document not found")

    chunk_count = (
        db.query(func.count(KBChunk.id))
        .filter(
            KBChunk.kb_document_id == kb_document_id,
            KBChunk.firm_id == claims.firm_id,
        )
        .scalar()
    )

    return {
        "id": kb_document.id,
        "firm_id": kb_document.firm_id,
        "title": kb_document.title,
        "document_type": kb_document.document_type,
        "s3_key": kb_document.s3_key,
        "lifecycle_state": kb_document.lifecycle_state,
        "created_at": kb_document.created_at.isoformat(),
        "updated_at": kb_document.updated_at.isoformat(),
        "chunk_count": chunk_count,
    }


@router.post("/kb/documents/{kb_document_id}/search")
def search_kb_document(
    *,
    kb_document_id: str,
    body: KBSearchRequest,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Semantic search within a firm's KB document."""
    kb_document = _get_kb_document(db, kb_document_id, claims.firm_id)
    if kb_document is None:
        raise HTTPException(status_code=404, detail="KB document not found")

    embedding_exists = (
        db.query(KBEmbedding.id)
        .join(KBChunk, KBChunk.id == KBEmbedding.kb_chunk_id)
        .filter(
            KBChunk.kb_document_id == kb_document_id,
            KBChunk.firm_id == claims.firm_id,
            KBEmbedding.firm_id == claims.firm_id,
        )
        .first()
    )
    if embedding_exists is None:
        return {
            "results": [],
            "reason": "not_indexed",
            "kb_document_id": kb_document_id,
        }

    try:
        query_vector = _embed_query(body.query)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "KB search query embedding failed for document %s", kb_document_id
        )
        raise HTTPException(status_code=503, detail="Query embedding failed")

    rows = db.execute(
        text(
            """
            SELECT kc.id, kc.text, kc.chunk_index,
                   ke.embedding <=> CAST(:query_vec AS vector) AS distance
            FROM kb_chunks kc
            JOIN kb_embeddings ke ON ke.kb_chunk_id = kc.id
            WHERE kc.firm_id = :firm_id
              AND kc.kb_document_id = :kb_document_id
              AND ke.firm_id = :firm_id
            ORDER BY distance
            LIMIT :top_k
            """
        ),
        {
            "query_vec": str(query_vector),
            "firm_id": claims.firm_id,
            "kb_document_id": kb_document_id,
            "top_k": body.top_k,
        },
    ).fetchall()

    return {
        "kb_document_id": kb_document_id,
        "results": [
            {
                "chunk_id": row[0],
                "text": row[1],
                "chunk_index": row[2],
                "distance": float(row[3]),
            }
            for row in rows
        ],
    }


@router.post("/kb/documents/{kb_document_id}/ingest", status_code=202)
async def ingest_kb_document_endpoint(
    *,
    kb_document_id: str,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Enqueue KB ingestion pipeline (Sprint 6B).

    Returns 202 Accepted with job_id. Poll GET /kb/documents/{id} for
    lifecycle_state = 'indexed' when ingestion completes.
    """
    from app.workers.enqueue import get_arq_pool, enqueue_ingest_kb_document

    kb_doc = _get_kb_document(db, kb_document_id, claims.firm_id)
    if kb_doc is None:
        raise HTTPException(status_code=404, detail="KB document not found")

    pool = await get_arq_pool()
    job_id = await enqueue_ingest_kb_document(
        pool,
        kb_document_id=kb_document_id,
        firm_id=claims.firm_id,
    )
    await pool.aclose()

    return {
        "status": "queued",
        "job_id": job_id,
        "kb_document_id": kb_document_id,
    }


@router.get("/kb/documents/{kb_document_id}/events")
def get_kb_document_events(
    *,
    kb_document_id: str,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Return all pipeline events for a KB document.

    Firm-scoped: confirms kb_document belongs to claims.firm_id before
    returning events. Events are identified by kb_document_id in detail JSONB.
    """
    from app.core.models import ProcessingEvent
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB

    kb_doc = _get_kb_document(db, kb_document_id, claims.firm_id)
    if kb_doc is None:
        raise HTTPException(status_code=404, detail="KB document not found")

    events = (
        db.query(ProcessingEvent)
        .filter(
            ProcessingEvent.detail["kb_document_id"].astext == kb_document_id
        )
        .order_by(ProcessingEvent.created_at.asc())
        .all()
    )

    return {
        "kb_document_id": kb_document_id,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "status": e.status,
                "detail": e.detail,
                "error_message": e.error_message,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }
