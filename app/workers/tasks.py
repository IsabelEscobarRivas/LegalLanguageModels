"""ARQ task definitions for async ingestion and classification pipelines.

Task naming convention: {pipeline}_{action}
All tasks carry firm_id in kwargs for ADR-009 compliance.
Workers validate firm_id on the task payload before executing.

Registered tasks:
  - ingest_document: extract → chunk → embed for case documents
  - ingest_kb_document: extract → chunk → embed for KB documents
  - classify_document_version: classify all chunks for a version
"""
import logging
import os

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.models import Document, KBDocument, Case

logger = logging.getLogger(__name__)


async def ingest_document(
    ctx: dict,
    *,
    document_id: str,
    case_id: str,
    firm_id: str,
    version_id: str,
) -> dict:
    """Extract, chunk, and embed a case document.

    Validates firm_id against the case before executing.
    Returns {"status": "ok"} or {"status": "failed", "reason": str}.
    """
    db: Session = SessionLocal()
    try:
        case = db.query(Case).filter(
            Case.id == case_id,
            Case.firm_id == firm_id,
        ).first()
        if case is None:
            logger.error(
                "ingest_document: firm_id mismatch or case not found "
                "case_id=%s firm_id=%s", case_id, firm_id
            )
            return {"status": "failed", "reason": "firm_boundary_violation"}

        from app.ingestion.service import process_document_version
        result = process_document_version(db, case_id, document_id, version_id)
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.exception(
            "ingest_document failed document_id=%s", document_id
        )
        return {"status": "failed", "reason": str(exc)}
    finally:
        db.close()


async def ingest_kb_document(
    ctx: dict,
    *,
    kb_document_id: str,
    firm_id: str,
) -> dict:
    """Extract, chunk, and embed a KB document.

    Validates firm_id against the KB document before executing.
    Returns {"status": "ok"} or {"status": "failed", "reason": str}.
    """
    db: Session = SessionLocal()
    try:
        kb_doc = db.query(KBDocument).filter(
            KBDocument.id == kb_document_id,
            KBDocument.firm_id == firm_id,
        ).first()
        if kb_doc is None:
            logger.error(
                "ingest_kb_document: firm_id mismatch or not found "
                "kb_document_id=%s firm_id=%s", kb_document_id, firm_id
            )
            return {"status": "failed", "reason": "firm_boundary_violation"}

        from app.kb.pipeline import chunk_kb_document, embed_kb_document, index_kb_document

        result = chunk_kb_document(db, kb_document_id, firm_id)
        if result["status"] not in ("ok", "exists"):
            return {"status": "failed", "reason": f"chunking: {result.get('reason')}"}

        result = embed_kb_document(db, kb_document_id, firm_id)
        if result["status"] == "failed":
            return {"status": "failed", "reason": f"embedding: {result.get('reason')}"}

        result = index_kb_document(db, kb_document_id, firm_id)
        if result["status"] != "ok":
            return {"status": "failed", "reason": f"indexing: {result.get('reason')}"}

        return {"status": "ok", "kb_document_id": kb_document_id}
    except Exception as exc:
        logger.exception(
            "ingest_kb_document failed kb_document_id=%s", kb_document_id
        )
        return {"status": "failed", "reason": str(exc)}
    finally:
        db.close()


async def classify_document_version(
    ctx: dict,
    *,
    case_id: str,
    document_id: str,
    version_id: str,
    visa_type: str,
    firm_id: str,
    force_reclassify: bool = False,
) -> dict:
    """Classify all chunks for a document version.

    Validates firm_id against the case before executing.
    Returns {"status": "ok"} or {"status": "failed", "reason": str}.
    """
    db: Session = SessionLocal()
    try:
        case = db.query(Case).filter(
            Case.id == case_id,
            Case.firm_id == firm_id,
        ).first()
        if case is None:
            logger.error(
                "classify_document_version: firm_id mismatch "
                "case_id=%s firm_id=%s", case_id, firm_id
            )
            return {"status": "failed", "reason": "firm_boundary_violation"}

        from app.classification.classifier import classify_document_version as _classify
        result = _classify(
            db, case_id, document_id, version_id,
            visa_type, force_reclassify=force_reclassify
        )
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.exception(
            "classify_document_version failed version_id=%s", version_id
        )
        return {"status": "failed", "reason": str(exc)}
    finally:
        db.close()
