"""Document ingestion orchestration.

Implements the V2 upload flow exactly as specified:

    validate case exists
    -> write document_received event
    -> upload raw file to S3
    -> write s3_upload_started / s3_upload_completed events
    -> INSERT Document (lifecycle_state='received')
    -> run extraction
    -> upload extracted text to S3 (if extraction succeeded)
    -> INSERT DocumentVersion fully populated (append-only)
    -> write text_extraction_completed / text_extraction_failed event
    -> UPDATE Document.lifecycle_state -> 'ingested' on success only

DocumentVersion rows are inserted once with their final values. They are never
updated after insertion — see the `info={'append_only': True}` marker on the
ORM model. Lifecycle changes happen on `Document`, which is not append-only.
"""
from datetime import datetime
from typing import Optional
import hashlib
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.models import Case, Document, DocumentVersion
from app.ingestion import s3 as s3_helper
from app.ingestion.events import write_event
from app.ingestion.extractor import assess_extraction_integrity, extract_text


logger = logging.getLogger(__name__)


class CaseNotFoundError(Exception):
    """Raised when the referenced case does not exist."""


class IngestionError(Exception):
    """Raised on unrecoverable ingestion failure (e.g. raw S3 upload failed)."""


def ingest_document(
    db: Session,
    case_id: str,
    file_bytes: bytes,
    original_filename: str,
    mime_type: Optional[str],
) -> dict:
    """Run the full ingestion pipeline for a single uploaded file.

    Returns a dict shaped for the router's `DocumentUploadResponse`. Raises
    `CaseNotFoundError` (-> 404) or `IngestionError` (-> 500) for the router
    to translate. Extraction failures do not raise — they are recorded on the
    `DocumentVersion` row as `extraction_status='failed'` and surfaced via the
    response.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise CaseNotFoundError(f"Case {case_id} not found")

    file_size = len(file_bytes)
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    document_id = str(uuid.uuid4())
    # Sprint 1 only handles the initial upload; future re-ingest paths will
    # compute the next version_number themselves.
    version_number = 1

    write_event(
        db,
        event_type="document_received",
        status="completed",
        case_id=case_id,
        detail={
            "original_name": original_filename,
            "mime_type": mime_type,
            "file_size": file_size,
        },
    )

    write_event(
        db,
        event_type="s3_upload_started",
        status="started",
        case_id=case_id,
        detail={"document_id": document_id, "version_number": version_number},
    )
    try:
        s3_raw_key = s3_helper.upload_raw_file(
            file_bytes=file_bytes,
            case_id=case_id,
            document_id=document_id,
            version_number=version_number,
            original_filename=original_filename,
            content_type=mime_type,
        )
    except Exception as exc:
        logger.exception("Raw S3 upload failed for case %s", case_id)
        write_event(
            db,
            event_type="s3_upload_failed",
            status="failed",
            case_id=case_id,
            detail={"document_id": document_id, "version_number": version_number},
            error_message=str(exc),
        )
        raise IngestionError("Failed to upload file to storage") from exc

    write_event(
        db,
        event_type="s3_upload_completed",
        status="completed",
        case_id=case_id,
        detail={
            "document_id": document_id,
            "version_number": version_number,
            "s3_raw_key": s3_raw_key,
        },
    )

    document = Document(
        id=document_id,
        case_id=case_id,
        original_name=original_filename,
        mime_type=mime_type,
        file_size=file_size,
        s3_raw_key=s3_raw_key,
        lifecycle_state="received",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    write_event(
        db,
        event_type="text_extraction_started",
        status="started",
        case_id=case_id,
        document_id=document_id,
        detail={"version_number": version_number},
    )

    extraction = extract_text(file_bytes, original_filename)
    integrity = assess_extraction_integrity(extraction, file_bytes)

    extracted_text_s3_key: Optional[str] = None
    final_extraction_status = extraction.status
    extraction_error_message: Optional[str] = None

    if extraction.status == "completed":
        try:
            extracted_text_s3_key = s3_helper.upload_extracted_text(
                text=extraction.text,
                case_id=case_id,
                document_id=document_id,
                version_number=version_number,
            )
        except Exception:
            logger.exception(
                "Extracted-text S3 upload failed for document %s", document_id
            )
            final_extraction_status = "failed"
            extraction_error_message = (
                "Text extraction succeeded but storing the extracted text failed"
            )
            extracted_text_s3_key = None

    version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=document_id,
        version_number=version_number,
        content_hash=content_hash,
        extraction_method=extraction.method,
        extraction_status=final_extraction_status,
        extracted_text_s3_key=extracted_text_s3_key,
        page_count=extraction.page_count,
        extraction_confidence=integrity["extraction_confidence"],
        text_density=integrity["text_density"],
        integrity_status=integrity["integrity_status"],
        # extracted_at records when extraction *succeeded*; left NULL on
        # failed/skipped so the audit trail isn't misleading.
        extracted_at=(
            datetime.utcnow() if final_extraction_status == "completed" else None
        ),
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    if not integrity["chunking_eligible"]:
        write_event(
            db,
            event_type="ingestion_integrity_failed",
            status="failed",
            case_id=case_id,
            document_id=document_id,
            document_version_id=version.id,
            detail={
                "integrity_status": integrity["integrity_status"],
                "extraction_confidence": integrity["extraction_confidence"],
                "text_density": integrity["text_density"],
                "document_id": document_id,
            },
        )
        document.lifecycle_state = "ingestion_failed"
        document.retrieval_eligible = False
        document.generation_eligible = False
        document.participation_state = "ingestion_failed"
        document.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(document)
        return {
            "document_id": document.id,
            "version_id": version.id,
            "version_number": version.version_number,
            "case_id": document.case_id,
            "original_name": document.original_name,
            "lifecycle_state": document.lifecycle_state,
            "extraction_status": version.extraction_status,
            "s3_raw_key": document.s3_raw_key,
            "created_at": document.created_at,
        }

    if final_extraction_status == "completed":
        write_event(
            db,
            event_type="text_extraction_completed",
            status="completed",
            case_id=case_id,
            document_id=document_id,
            document_version_id=version.id,
            detail={
                "extraction_method": extraction.method,
                "page_count": extraction.page_count,
                "extracted_text_s3_key": extracted_text_s3_key,
            },
        )
        document.lifecycle_state = "ingested"
        document.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(document)
    else:
        write_event(
            db,
            event_type="text_extraction_failed",
            status="failed",
            case_id=case_id,
            document_id=document_id,
            document_version_id=version.id,
            detail={
                "result_status": extraction.status,
                "attempted_method": extraction.method,
            },
            error_message=extraction_error_message,
        )

    return {
        "document_id": document.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "case_id": document.case_id,
        "original_name": document.original_name,
        "lifecycle_state": document.lifecycle_state,
        "extraction_status": version.extraction_status,
        "s3_raw_key": document.s3_raw_key,
        "created_at": document.created_at,
    }
