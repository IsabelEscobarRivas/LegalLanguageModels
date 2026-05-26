import logging

from sqlalchemy.orm import Session

from app.classification.coverage import evaluate_coverage


logger = logging.getLogger(__name__)

COVERAGE_GATE_STATUSES = {"covered", "insufficient"}
GENERATION_BLOCKED_STATUS = "missing"


def check_coverage_gate(
    db: Session,
    case_id: str,
    visa_type: str,
    force_generate: bool = False,
) -> dict:
    """Evaluate coverage and determine whether generation may proceed.

    Returns a gate result dict with keys:
        allowed: bool — whether generation may proceed
        overall_status: str — 'complete', 'incomplete', or 'coverage_override'
        missing_criteria: list[str] — criteria codes with gap_status='missing'
        insufficient_criteria: list[str] — criteria codes with gap_status='insufficient'
        coverage_detail: list[dict] — full coverage result from evaluate_coverage
        override_available: bool — always True when allowed=False

    Rules:
        - If all criteria are 'covered': allowed=True, overall_status='complete'
        - If any criteria are 'missing' AND force_generate=False: allowed=False
        - If any criteria are 'missing' AND force_generate=True: allowed=True, overall_status='coverage_override'
        - 'insufficient' criteria do not block generation — they are flagged only
        - If evaluate_coverage fails: allowed=False, treat as incomplete

    Never raises.
    """
    try:
        coverage_result = evaluate_coverage(db, case_id, visa_type)

        if coverage_result.get("status") != "ok":
            logger.warning(
                "Coverage evaluation failed for case_id=%s: %s",
                case_id,
                coverage_result.get("reason"),
            )
            return {
                "allowed": False,
                "overall_status": "incomplete",
                "missing_criteria": [],
                "insufficient_criteria": [],
                "coverage_detail": [],
                "override_available": True,
            }

        coverage = coverage_result.get("coverage", [])
        missing = [
            c["criteria_code"] for c in coverage if c["gap_status"] == "missing"
        ]
        insufficient = [
            c["criteria_code"]
            for c in coverage
            if c["gap_status"] == "insufficient"
        ]

        if not missing:
            return {
                "allowed": True,
                "overall_status": "complete",
                "missing_criteria": [],
                "insufficient_criteria": insufficient,
                "coverage_detail": coverage,
                "override_available": False,
            }

        if force_generate:
            logger.warning(
                "Coverage gate overridden for case_id=%s missing=%s",
                case_id,
                missing,
            )
            return {
                "allowed": True,
                "overall_status": "coverage_override",
                "missing_criteria": missing,
                "insufficient_criteria": insufficient,
                "coverage_detail": coverage,
                "override_available": False,
            }

        return {
            "allowed": False,
            "overall_status": "incomplete",
            "missing_criteria": missing,
            "insufficient_criteria": insufficient,
            "coverage_detail": coverage,
            "override_available": True,
        }

    except Exception:
        logger.exception(
            "Unexpected error in coverage gate for case_id=%s", case_id
        )
        return {
            "allowed": False,
            "overall_status": "incomplete",
            "missing_criteria": [],
            "insufficient_criteria": [],
            "coverage_detail": [],
            "override_available": True,
        }
