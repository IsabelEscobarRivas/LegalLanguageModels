"""Effective classification resolution.

Given a ClassificationResult and its associated ClassificationFeedback rows,
resolves the effective classification that downstream retrieval should use.

Resolution is deterministic:
  latest 'corrected' feedback wins over original
  latest 'confirmed' feedback preserves original
  'rejected' feedback excludes chunk from retrieval
  no feedback → original classification

Original ClassificationResult rows are never mutated.
"""
from sqlalchemy.orm import Session

from app.core.models import ClassificationFeedback, ClassificationResult


def resolve_effective_classification(
    db: Session,
    classification_result_id: str,
) -> dict:
    """Return the effective classification for downstream use.

    Never raises. Returns {"status": "not_found"} if result doesn't exist.
    """
    result = db.query(ClassificationResult).filter(
        ClassificationResult.id == classification_result_id
    ).first()
    if result is None:
        return {"status": "not_found"}

    latest_feedback = (
        db.query(ClassificationFeedback)
        .filter(
            ClassificationFeedback.classification_result_id == classification_result_id,
            ClassificationFeedback.action.in_(["confirmed", "corrected", "rejected"]),
        )
        .order_by(ClassificationFeedback.created_at.desc())
        .first()
    )

    if latest_feedback is None:
        return {
            "status": "ok",
            "override_applied": False,
            "feedback_id": None,
            "criteria_id": result.criteria_id,
            "section_affinity_id": result.section_affinity_id,
            "confidence_score": result.confidence_score,
            "excluded": False,
        }

    if latest_feedback.action == "rejected":
        return {
            "status": "ok",
            "override_applied": True,
            "feedback_id": latest_feedback.id,
            "excluded": True,
            "reason": "reviewer_rejected",
        }

    return {
        "status": "ok",
        "override_applied": latest_feedback.action == "corrected",
        "feedback_id": latest_feedback.id,
        "criteria_id": (
            latest_feedback.corrected_criteria_id or result.criteria_id
        ),
        "section_affinity_id": (
            latest_feedback.corrected_section_affinity_id
            or result.section_affinity_id
        ),
        "confidence_score": (
            latest_feedback.corrected_confidence_score
            or result.confidence_score
        ),
        "excluded": False,
    }
