"""Document-level endpoints.

POST /cases/{case_id}/documents
GET  /cases/{case_id}/documents/{document_id}
GET  /cases/{case_id}/documents/{document_id}/versions
GET  /cases/{case_id}/documents/{document_id}/versions/{version_id}/events
"""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Document, DocumentVersion, ProcessingEvent
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


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=201,
)
async def upload_document(
    case_id: str,
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
    case_id: str, document_id: str, db: Session = Depends(get_db)
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
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/versions",
    response_model=DocumentVersionList,
)
def list_document_versions(
    case_id: str, document_id: str, db: Session = Depends(get_db)
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
    case_id: str,
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
