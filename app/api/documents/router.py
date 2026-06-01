"""Document-level endpoints.

POST /cases/{case_id}/documents
GET  /cases/{case_id}/documents/{document_id}
GET  /cases/{case_id}/documents/{document_id}/versions
GET  /cases/{case_id}/documents/{document_id}/versions/{version_id}/events
POST /cases/{case_id}/documents/{document_id}/participation
GET  /cases/{case_id}/documents/{document_id}/participation
"""
import logging
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import TokenClaims, get_current_claims, require_case_access
from app.core.database import get_db
from app.core.models import (
    Case,
    Chunk,
    ClassificationResult,
    Document,
    DocumentParticipationEvent,
    DocumentVersion,
    DraftSection,
    GenerationTrace,
    ProcessingEvent,
)
from app.core.schemas import (
    DocumentDetail,
    DocumentUploadResponse,
    DocumentVersionList,
    DocumentVersionSummary,
    LatestVersion,
    ProcessingEventResponse,
    VersionEventList,
)
from app.ingestion.service import (
    CaseNotFoundError,
    IngestionError,
    ingest_document,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


def _evidence_excerpt_count(db: Session, document_id: str) -> int:
    return (
        db.query(func.count(Chunk.id))
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .filter(DocumentVersion.document_id == document_id)
        .scalar()
        or 0
    )


def _classification_count(db: Session, document_id: str) -> int:
    return (
        db.query(func.count(ClassificationResult.id))
        .join(Chunk, Chunk.id == ClassificationResult.chunk_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .filter(DocumentVersion.document_id == document_id)
        .scalar()
        or 0
    )


def _draft_section_contributions(db: Session, document_id: str) -> list[str]:
    rows = (
        db.query(DraftSection.section_code)
        .join(GenerationTrace, GenerationTrace.draft_section_id == DraftSection.id)
        .join(Chunk, Chunk.id == GenerationTrace.chunk_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .filter(DocumentVersion.document_id == document_id)
        .distinct()
        .order_by(DraftSection.section_code)
        .all()
    )
    return [row[0] for row in rows]


class ParticipationRequest(BaseModel):
    action: Literal[
        "excluded_from_retrieval",
        "excluded_from_generation",
        "archived",
        "quarantined",
        "superseded",
        "restored",
    ]
    reason: Optional[str] = None


PARTICIPATION_ACTION_MAP = {
    "excluded_from_retrieval": {
        "participation_state": "excluded_from_retrieval",
        "retrieval_eligible": False,
        "generation_eligible": False,
    },
    "excluded_from_generation": {
        "participation_state": "excluded_from_generation",
        "retrieval_eligible": True,
        "generation_eligible": False,
    },
    "archived": {
        "participation_state": "archived",
        "retrieval_eligible": False,
        "generation_eligible": False,
    },
    "quarantined": {
        "participation_state": "quarantined",
        "retrieval_eligible": False,
        "generation_eligible": False,
    },
    "superseded": {
        "participation_state": "superseded",
        "retrieval_eligible": False,
        "generation_eligible": False,
    },
    "restored": {
        "participation_state": "active",
        "retrieval_eligible": True,
        "generation_eligible": True,
    },
}


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=201,
)
async def upload_document(
    *,
    case_id: str = Depends(require_case_access),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    file_bytes = await file.read()
    try:
        result = ingest_document(
            db=db,
            case_id=case_id,
            file_bytes=file_bytes,
            original_filename=file.filename or "untitled",
            mime_type=file.content_type,
        )
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except IngestionError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception:
        logger.exception("Unexpected ingestion failure for case %s", case_id)
        raise HTTPException(status_code=500, detail="Ingestion failed")
    return DocumentUploadResponse(**result)


@router.get(
    "/cases/{case_id}/documents/{document_id}",
    response_model=DocumentDetail,
)
def get_document(
    *,
    case_id: str = Depends(require_case_access),
    document_id: str,
    db: Session = Depends(get_db),
) -> DocumentDetail:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.case_id == case_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    latest = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )

    latest_version = (
        LatestVersion(
            id=latest.id,
            version_number=latest.version_number,
            extraction_status=latest.extraction_status,
            extracted_at=latest.extracted_at,
        )
        if latest is not None
        else None
    )

    return DocumentDetail(
        id=document.id,
        case_id=document.case_id,
        original_name=document.original_name,
        mime_type=document.mime_type,
        file_size=document.file_size,
        lifecycle_state=document.lifecycle_state,
        s3_raw_key=document.s3_raw_key,
        created_at=document.created_at,
        latest_version=latest_version,
        extraction_method=latest.extraction_method if latest is not None else None,
        extraction_status=latest.extraction_status if latest is not None else None,
        extraction_confidence=latest.extraction_confidence if latest is not None else None,
        text_density=latest.text_density if latest is not None else None,
        integrity_status=latest.integrity_status if latest is not None else None,
        page_count=latest.page_count if latest is not None else None,
        retrieval_eligible=document.retrieval_eligible,
        generation_eligible=document.generation_eligible,
        participation_state=document.participation_state,
        evidence_excerpt_count=_evidence_excerpt_count(db, document_id),
        classification_count=_classification_count(db, document_id),
        draft_section_contributions=_draft_section_contributions(db, document_id),
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/versions",
    response_model=DocumentVersionList,
)
def list_document_versions(
    *,
    case_id: str = Depends(require_case_access),
    document_id: str,
    db: Session = Depends(get_db),
) -> DocumentVersionList:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.case_id == case_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.asc())
        .all()
    )

    return DocumentVersionList(
        document_id=document_id,
        versions=[DocumentVersionSummary.model_validate(v) for v in versions],
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/versions/{version_id}/events",
    response_model=VersionEventList,
)
def list_version_events(
    *,
    case_id: str = Depends(require_case_access),
    document_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> VersionEventList:
    version = (
        db.query(DocumentVersion)
        .join(Document, Document.id == DocumentVersion.document_id)
        .filter(
            DocumentVersion.id == version_id,
            Document.id == document_id,
            Document.case_id == case_id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    events = (
        db.query(ProcessingEvent)
        .filter(ProcessingEvent.document_version_id == version_id)
        .order_by(ProcessingEvent.created_at.asc())
        .all()
    )

    return VersionEventList(
        version_id=version_id,
        events=[ProcessingEventResponse.model_validate(e) for e in events],
    )


@router.post("/cases/{case_id}/documents/{document_id}/participation")
def update_document_participation(
    *,
    case_id: str = Depends(require_case_access),
    document_id: str,
    body: ParticipationRequest,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .join(Case, Case.id == Document.case_id)
        .filter(
            Document.id == document_id,
            Document.case_id == case_id,
            Case.firm_id == claims.firm_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    previous_state = document.participation_state
    mapping = PARTICIPATION_ACTION_MAP[body.action]
    new_state = mapping["participation_state"]

    document.participation_state = new_state
    document.retrieval_eligible = mapping["retrieval_eligible"]
    document.generation_eligible = mapping["generation_eligible"]
    document.updated_at = datetime.utcnow()

    event = DocumentParticipationEvent(
        id=str(uuid.uuid4()),
        document_id=document.id,
        case_id=case_id,
        firm_id=claims.firm_id,
        actor_id=claims.sub,
        action=body.action,
        previous_state=previous_state,
        new_state=new_state,
        reason=body.reason,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "document_id": document.id,
        "previous_state": previous_state,
        "new_state": new_state,
        "action": body.action,
        "created_at": event.created_at.isoformat(),
    }


@router.get("/cases/{case_id}/documents/{document_id}/participation")
def get_document_participation_history(
    *,
    case_id: str = Depends(require_case_access),
    document_id: str,
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.case_id == case_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    events = (
        db.query(DocumentParticipationEvent)
        .filter(DocumentParticipationEvent.document_id == document_id)
        .order_by(DocumentParticipationEvent.created_at.desc())
        .all()
    )

    return {
        "document_id": document_id,
        "events": [
            {
                "id": event.id,
                "document_id": event.document_id,
                "case_id": event.case_id,
                "firm_id": event.firm_id,
                "actor_id": event.actor_id,
                "action": event.action,
                "previous_state": event.previous_state,
                "new_state": event.new_state,
                "reason": event.reason,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    }
