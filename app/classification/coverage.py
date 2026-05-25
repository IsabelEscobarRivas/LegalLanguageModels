"""Coverage gap detection (S3-D07)."""
import logging
import uuid
from datetime import datetime

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.models import ClassificationResult, CriteriaReference


logger = logging.getLogger(__name__)


def evaluate_coverage(
    db: Session,
    case_id: str,
    visa_type: str,
) -> dict:
    """Evaluate USCIS criteria coverage for a case. Never raises."""
    try:
        criteria = (
            db.query(CriteriaReference)
            .filter(
                CriteriaReference.visa_type.in_([visa_type, "BOTH"]),
                CriteriaReference.is_active.is_(True),
            )
            .order_by(CriteriaReference.display_order.asc())
            .all()
        )

        evaluated_at = datetime.utcnow()
        coverage_rows: list[dict] = []

        for criterion in criteria:
            count = (
                db.query(
                    func.count(func.distinct(ClassificationResult.chunk_id))
                )
                .filter(
                    ClassificationResult.case_id == case_id,
                    ClassificationResult.criteria_id == criterion.id,
                )
                .scalar()
            ) or 0

            if count == 0:
                gap_status = "missing"
            elif count == 1:
                gap_status = "insufficient"
            else:
                gap_status = "covered"

            db.execute(
                text(
                    """
                    INSERT INTO coverage_gaps (
                        id, case_id, criteria_id, gap_status, chunk_count, evaluated_at
                    )
                    VALUES (
                        :id, :case_id, :criteria_id, :gap_status, :chunk_count, NOW()
                    )
                    ON CONFLICT (case_id, criteria_id)
                    DO UPDATE SET
                        gap_status = EXCLUDED.gap_status,
                        chunk_count = EXCLUDED.chunk_count,
                        evaluated_at = NOW()
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "case_id": case_id,
                    "criteria_id": criterion.id,
                    "gap_status": gap_status,
                    "chunk_count": count,
                },
            )

            coverage_rows.append(
                {
                    "criteria_id": criterion.id,
                    "criteria_code": criterion.code,
                    "criteria_label": criterion.label,
                    "gap_status": gap_status,
                    "chunk_count": count,
                }
            )

        db.commit()

        overall_status = (
            "complete"
            if coverage_rows
            and all(row["gap_status"] == "covered" for row in coverage_rows)
            else "incomplete"
        )

        return {
            "status": "ok",
            "case_id": case_id,
            "visa_type": visa_type,
            "overall_status": overall_status,
            "evaluated_at": evaluated_at.isoformat(),
            "coverage": coverage_rows,
        }

    except Exception as exc:
        logger.exception("Coverage evaluation failed for case %s", case_id)
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after coverage failure also failed")
        return {"status": "failed", "reason": str(exc)}
