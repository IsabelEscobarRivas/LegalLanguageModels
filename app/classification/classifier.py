"""Classification pipeline for Sprint 3.

LLM-based dual-axis classification: USCIS criteria mapping + section affinity.
Persists append-only `ClassificationResult` rows per qualifying criterion match.

Public API:
  - classify_chunk(db, case_id, chunk_id, visa_type, force_reclassify=False)
  - classify_document_version(db, case_id, document_id, version_id, visa_type, ...)

Event taxonomy: classification_completed, classification_failed
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

import openai
from sqlalchemy.orm import Session

from app.core.models import (
    Chunk,
    ClassificationResult,
    CriteriaReference,
    Document,
    DocumentVersion,
    ProcessingEvent,
    SectionAffinityReference,
)
from app.ingestion.events import write_event


logger = logging.getLogger(__name__)


CLASSIFICATION_MODEL = os.environ.get("CLASSIFICATION_MODEL", "gpt-4o")
CLASSIFICATION_MODEL_VERSION = os.environ.get(
    "CLASSIFICATION_MODEL_VERSION", "1.0"
)
CLASSIFICATION_CONFIDENCE_THRESHOLD = float(
    os.environ.get("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.5")
)

_VALID_SECTION_AFFINITY_CODES = frozenset(
    {
        "background",
        "experience",
        "expert_opinion",
        "achievements",
        "impact",
        "conclusion",
    }
)


def _safe_default_classification() -> dict[str, Any]:
    return {
        "supports": False,
        "confidence": 0.0,
        "rationale": "Invalid model response",
        "section_affinity": "background",
        "citation_text": None,
    }


def _classify_chunk_against_criterion(
    chunk_text: str, criterion: CriteriaReference
) -> dict[str, Any]:
    """Call the LLM classifier for one chunk/criterion pair. Never raises."""
    system_prompt = """You are a legal document classifier for US immigration petitions.
Analyze whether the provided text supports the given USCIS criterion.
Respond ONLY with valid JSON matching this exact schema:
{
  "supports": boolean,
  "confidence": float between 0.0 and 1.0,
  "rationale": "one or two sentence explanation",
  "section_affinity": one of: "background", "experience", "expert_opinion", "achievements", "impact", "conclusion",
  "citation_text": "the single most probative sentence or phrase from the text that supports this criterion, or null if supports is false"
}
If the text does not support the criterion, set supports=false, confidence=0.0, and citation_text=null.
citation_text must be an exact quote or very close paraphrase of a specific passage from the provided text.
citation_text must never introduce facts not present in the provided text.
citation_text must be null when supports is false."""

    user_prompt = f"""CRITERION: {criterion.label}
DESCRIPTION: {criterion.description}

TEXT TO CLASSIFY:
{chunk_text}"""

    try:
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=CLASSIFICATION_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        result = json.loads(response.choices[0].message.content)

        supports = result.get("supports")
        confidence = result.get("confidence")
        rationale = result.get("rationale")
        section_affinity = result.get("section_affinity")

        if not isinstance(supports, bool):
            return _safe_default_classification()
        if not isinstance(confidence, (int, float)):
            return _safe_default_classification()
        confidence = float(confidence)
        if confidence < 0.0 or confidence > 1.0:
            return _safe_default_classification()
        if not isinstance(rationale, str):
            return _safe_default_classification()
        if (
            not isinstance(section_affinity, str)
            or section_affinity not in _VALID_SECTION_AFFINITY_CODES
        ):
            return _safe_default_classification()

        citation_text = result.get("citation_text")
        if citation_text is not None and not isinstance(citation_text, str):
            citation_text = None
        if citation_text is not None and not citation_text.strip():
            citation_text = None

        return {
            "supports": supports,
            "confidence": confidence,
            "rationale": rationale,
            "section_affinity": section_affinity,
            "citation_text": citation_text,
        }
    except Exception:
        logger.exception(
            "LLM classification failed for criterion %s", criterion.code
        )
        return _safe_default_classification()


def _resolve_section_affinity(
    db: Session,
    criteria_id: str,
    visa_type: str,
    llm_section_code: str,
) -> Optional[str]:
    """Returns section_affinity_id or None if unresolvable.

    Priority:
    1. Fetch default from criteria_section_affinity_defaults
    2. If LLM code is valid and differs from default, use LLM override
    3. If LLM code is invalid, use default
    4. If no default, use LLM code directly
    5. If neither resolves, return None
    """
    from app.core.models import CriteriaSectionAffinityDefault, SectionAffinityReference

    default_row = (
        db.query(CriteriaSectionAffinityDefault)
        .filter(
            CriteriaSectionAffinityDefault.criteria_id == criteria_id,
            CriteriaSectionAffinityDefault.visa_type.in_([visa_type, "BOTH"]),
        )
        .order_by(CriteriaSectionAffinityDefault.priority.asc())
        .first()
    )

    llm_section = (
        db.query(SectionAffinityReference)
        .filter(SectionAffinityReference.code == llm_section_code)
        .first()
    )

    if default_row and llm_section and llm_section.id != default_row.section_affinity_id:
        return llm_section.id
    elif default_row:
        return default_row.section_affinity_id
    elif llm_section:
        return llm_section.id
    else:
        logger.warning(
            "Could not resolve section affinity for criteria_id=%s visa_type=%s llm_code=%s",
            criteria_id,
            visa_type,
            llm_section_code,
        )
        return None


def _classification_rows_to_dicts(
    db: Session, chunk_id: str
) -> list[dict[str, Any]]:
    """Load existing classification rows for a chunk with joined reference labels."""
    rows = (
        db.query(
            ClassificationResult,
            CriteriaReference,
            SectionAffinityReference,
        )
        .join(
            CriteriaReference,
            CriteriaReference.id == ClassificationResult.criteria_id,
        )
        .join(
            SectionAffinityReference,
            SectionAffinityReference.id
            == ClassificationResult.section_affinity_id,
        )
        .filter(ClassificationResult.chunk_id == chunk_id)
        .order_by(CriteriaReference.display_order.asc())
        .all()
    )
    return [
        {
            "id": result.id,
            "criteria_code": criterion.code,
            "criteria_label": criterion.label,
            "section_affinity": section.code,
            "confidence_score": result.confidence_score,
            "rationale": result.rationale,
            "citation_text": result.citation_text,
        }
        for result, criterion, section in rows
    ]


def classify_chunk(
    db: Session,
    case_id: str,
    chunk_id: str,
    visa_type: str,
    force_reclassify: bool = False,
) -> dict[str, Any]:
    """Classify one chunk against all active criteria for a visa type. Never raises."""
    document_id: str | None = None
    version_id: str | None = None

    try:
        row = (
            db.query(Chunk, DocumentVersion, Document)
            .join(
                DocumentVersion,
                DocumentVersion.id == Chunk.document_version_id,
            )
            .join(Document, Document.id == DocumentVersion.document_id)
            .filter(Chunk.id == chunk_id, Document.case_id == case_id)
            .first()
        )
        if row is None:
            return {"status": "not_found"}

        chunk, version, document = row
        document_id = document.id
        version_id = version.id

        if not force_reclassify:
            existing = (
                db.query(ClassificationResult.id)
                .filter(ClassificationResult.chunk_id == chunk_id)
                .first()
            )
            if existing is not None:
                return {
                    "status": "exists",
                    "classifications": _classification_rows_to_dicts(
                        db, chunk_id
                    ),
                }

        criteria = (
            db.query(CriteriaReference)
            .filter(
                CriteriaReference.visa_type.in_([visa_type, "BOTH"]),
                CriteriaReference.is_active.is_(True),
            )
            .order_by(CriteriaReference.display_order.asc())
            .all()
        )
        if not criteria:
            write_event(
                db,
                event_type="classification_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={"chunk_id": chunk_id, "reason": "no_criteria_found"},
                error_message="No active criteria found for visa type",
            )
            return {"status": "failed", "reason": "no_criteria_found"}

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            write_event(
                db,
                event_type="classification_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={"chunk_id": chunk_id, "reason": "missing_api_key"},
                error_message="OPENAI_API_KEY is not set",
            )
            return {"status": "failed", "reason": "missing_api_key"}

        section_by_id = {
            s.id: s for s in db.query(SectionAffinityReference).all()
        }

        result_objects: list[ClassificationResult] = []
        response_dicts: list[dict[str, Any]] = []

        for criterion in criteria:
            llm_result = _classify_chunk_against_criterion(chunk.text, criterion)
            if not llm_result["supports"]:
                continue
            if llm_result["confidence"] < CLASSIFICATION_CONFIDENCE_THRESHOLD:
                continue

            section_affinity_id = _resolve_section_affinity(
                db,
                criterion.id,
                visa_type,
                llm_result["section_affinity"],
            )
            if section_affinity_id is None:
                continue

            section = section_by_id.get(section_affinity_id)
            if section is None:
                continue

            result_id = str(uuid.uuid4())
            result_objects.append(
                ClassificationResult(
                    id=result_id,
                    chunk_id=chunk.id,
                    document_version_id=version.id,
                    case_id=case_id,
                    criteria_id=criterion.id,
                    section_affinity_id=section_affinity_id,
                    confidence_score=llm_result["confidence"],
                    rationale=llm_result["rationale"],
                    model_name=CLASSIFICATION_MODEL,
                    model_version=CLASSIFICATION_MODEL_VERSION,
                    classifier_type="llm",
                    citation_text=llm_result.get("citation_text"),
                )
            )
            response_dicts.append(
                {
                    "id": result_id,
                    "criteria_code": criterion.code,
                    "criteria_label": criterion.label,
                    "section_affinity": section.code,
                    "confidence_score": llm_result["confidence"],
                    "rationale": llm_result["rationale"],
                    "citation_text": llm_result.get("citation_text"),
                }
            )

        classifications_created = len(result_objects)
        chunks_with_no_match = 1 if classifications_created == 0 else 0

        if result_objects:
            db.bulk_save_objects(result_objects)

        event = ProcessingEvent(
            case_id=case_id,
            document_id=document_id,
            document_version_id=version_id,
            event_type="classification_completed",
            status="completed",
            detail={
                "chunk_id": chunk_id,
                "classifications_created": classifications_created,
                "chunks_with_no_match": chunks_with_no_match,
            },
        )
        db.add(event)

        if classifications_created > 0 and document.lifecycle_state == "embedded":
            document.lifecycle_state = "indexed"
            document.updated_at = datetime.utcnow()

        db.commit()

        return {
            "status": "ok",
            "chunk_id": chunk_id,
            "classifications_created": classifications_created,
            "classifications": response_dicts,
        }

    except Exception as exc:
        logger.exception("Classification failed unexpectedly for chunk %s", chunk_id)
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after classification failure also failed")
        write_event(
            db,
            event_type="classification_failed",
            status="failed",
            case_id=case_id,
            document_id=document_id,
            document_version_id=version_id,
            detail={"chunk_id": chunk_id, "reason": "exception"},
            error_message=str(exc),
        )
        return {"status": "failed", "reason": str(exc)}


def classify_document_version(
    db: Session,
    case_id: str,
    document_id: str,
    version_id: str,
    visa_type: str,
    force_reclassify: bool = False,
) -> dict[str, Any]:
    """Classify all chunks for a DocumentVersion. Never raises."""
    try:
        document = (
            db.query(Document)
            .filter(Document.id == document_id, Document.case_id == case_id)
            .first()
        )
        if document is None:
            return {"status": "not_found"}

        version = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.id == version_id,
                DocumentVersion.document_id == document_id,
            )
            .first()
        )
        if version is None:
            return {"status": "not_found"}

        chunks = (
            db.query(Chunk)
            .filter(Chunk.document_version_id == version_id)
            .order_by(Chunk.chunk_index.asc())
            .all()
        )
        if not chunks:
            return {"status": "failed", "reason": "no_chunks"}

        chunks_processed = 0
        classifications_created = 0
        chunks_with_no_match = 0
        chunks_failed = 0

        for chunk in chunks:
            result = classify_chunk(
                db,
                case_id,
                chunk.id,
                visa_type,
                force_reclassify=force_reclassify,
            )
            status_val = result["status"]

            if status_val == "not_found":
                return {"status": "not_found"}

            if status_val == "failed":
                chunks_failed += 1
                chunks_processed += 1
                continue

            chunks_processed += 1

            if status_val == "exists":
                if len(result.get("classifications", [])) == 0:
                    chunks_with_no_match += 1
                continue

            if status_val == "ok":
                created = result.get("classifications_created", 0)
                classifications_created += created
                if created == 0:
                    chunks_with_no_match += 1

        return {
            "status": "ok",
            "version_id": version_id,
            "chunks_processed": chunks_processed,
            "classifications_created": classifications_created,
            "chunks_with_no_match": chunks_with_no_match,
            "chunks_failed": chunks_failed,
        }

    except Exception as exc:
        logger.exception(
            "Classification failed unexpectedly for version %s", version_id
        )
        return {"status": "failed", "reason": str(exc)}
