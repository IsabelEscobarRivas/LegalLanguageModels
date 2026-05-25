"""Classification feedback workflow (S3-D06)."""
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.models import (
    ClassificationFeedback,
    ClassificationResult,
    CriteriaReference,
    SectionAffinityReference,
)


logger = logging.getLogger(__name__)


def submit_feedback(
    db: Session,
    case_id: str,
    classification_result_id: str,
    reviewer_id: str,
    action: str,
    corrected_criteria_id: Optional[str] = None,
    corrected_section_affinity_id: Optional[str] = None,
    corrected_confidence_score: Optional[float] = None,
    rationale: Optional[str] = None,
) -> dict:
    """Record human feedback on a classification result. Never raises."""
    try:
        result_row = (
            db.query(ClassificationResult)
            .filter(ClassificationResult.id == classification_result_id)
            .first()
        )
        if result_row is None or result_row.case_id != case_id:
            return {"status": "not_found"}

        if action == "corrected":
            if corrected_criteria_id is not None:
                criteria = (
                    db.query(CriteriaReference)
                    .filter(
                        CriteriaReference.id == corrected_criteria_id,
                        CriteriaReference.is_active.is_(True),
                    )
                    .first()
                )
                if criteria is None:
                    return {
                        "status": "invalid",
                        "reason": "corrected_criteria_id not found",
                    }
            if corrected_section_affinity_id is not None:
                section = (
                    db.query(SectionAffinityReference)
                    .filter(
                        SectionAffinityReference.id
                        == corrected_section_affinity_id,
                    )
                    .first()
                )
                if section is None:
                    return {
                        "status": "invalid",
                        "reason": "corrected_section_affinity_id not found",
                    }

        feedback = ClassificationFeedback(
            id=str(uuid.uuid4()),
            classification_result_id=classification_result_id,
            case_id=case_id,
            reviewer_id=reviewer_id,
            action=action,
            corrected_criteria_id=corrected_criteria_id,
            corrected_section_affinity_id=corrected_section_affinity_id,
            corrected_confidence_score=corrected_confidence_score,
            rationale=rationale,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        return {
            "status": "ok",
            "id": feedback.id,
            "classification_result_id": classification_result_id,
            "action": action,
            "created_at": feedback.created_at.isoformat(),
        }

    except Exception as exc:
        logger.exception(
            "Feedback submission failed for classification result %s",
            classification_result_id,
        )
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after feedback failure also failed")
        return {"status": "failed", "reason": str(exc)}
