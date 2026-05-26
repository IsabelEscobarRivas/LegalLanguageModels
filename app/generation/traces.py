import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.models import GenerationTrace


logger = logging.getLogger(__name__)


def write_generation_traces(
    db: Session,
    draft_section_id: str,
    classification_results: list[dict],
) -> int:
    """Persist generation traces for a draft section.

    One GenerationTrace row per classification_result used in generation.
    classification_results is a list of dicts with keys:
        classification_result_id: str
        chunk_id: str
        citation_text: str | None
        similarity_score: float | None

    Returns count of traces written.
    Never raises — failures are logged and swallowed.
    Rolls back and returns 0 on any exception.
    """
    if not classification_results:
        return 0

    try:
        traces = [
            GenerationTrace(
                id=str(uuid.uuid4()),
                draft_section_id=draft_section_id,
                chunk_id=cr["chunk_id"],
                classification_result_id=cr["classification_result_id"],
                citation_text=cr.get("citation_text"),
                similarity_score=cr.get("similarity_score"),
            )
            for cr in classification_results
        ]
        db.bulk_save_objects(traces)
        db.commit()
        return len(traces)
    except Exception:
        logger.exception(
            "Failed to write generation traces for draft_section_id=%s",
            draft_section_id,
        )
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after trace write failure also failed")
        return 0


def build_trace_dicts(
    classification_results: list[dict],
) -> list[dict]:
    """Build trace dicts for API response inclusion.

    Returns list of dicts with provenance fields for each result used.
    Does not touch the DB.
    """
    return [
        {
            "chunk_id": cr["chunk_id"],
            "classification_result_id": cr["classification_result_id"],
            "citation_text": cr.get("citation_text"),
            "similarity_score": cr.get("similarity_score"),
        }
        for cr in classification_results
    ]
