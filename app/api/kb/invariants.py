"""Provenance separation invariant checks.

These queries validate that KB guidance has never entered evidentiary
provenance chains. They are intended for QA, CI, and operational auditing.

The core invariant:

  SELECT COUNT(*) FROM generation_traces gt
  JOIN kb_chunks kc ON kc.id = gt.chunk_id;

Must always return 0.

This is a permanent platform invariant. It cannot be relaxed without
revising ADR-004 and ADR-010 through formal architectural review.

Why this is permanent:
  generation_traces records evidence provenance — the chain from a classified
  document chunk to a draft section. This chain is the platform's legal audit
  trail. If KB chunk IDs ever appear in this chain, the audit trail becomes
  legally unreliable: a USCIS adjudicator reading a generation trace would
  believe firm-internal style preferences are case evidence.

  The structural separation (separate FK targets, no shared chunk namespace)
  is the mechanical enforcement. This query is the verification.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text


def check_provenance_separation(db: Session) -> dict:
    """Verify KB chunks have never entered generation_traces.

    Returns:
      {"status": "ok", "violation_count": 0} — invariant holds
      {"status": "violated", "violation_count": N} — CRITICAL — alert immediately
    """
    result = db.execute(text(
        """
        SELECT COUNT(*) FROM generation_traces gt
        JOIN kb_chunks kc ON kc.id = gt.chunk_id
        """
    )).scalar()

    count = int(result or 0)
    if count == 0:
        return {"status": "ok", "violation_count": 0}
    return {
        "status": "violated",
        "violation_count": count,
        "message": (
            "CRITICAL: KB chunk IDs found in generation_traces. "
            "Evidence provenance chain is compromised. "
            "Halt generation and investigate immediately."
        ),
    }


def check_kb_guidance_trace_isolation(db: Session) -> dict:
    """Verify kb_guidance_traces has no chunk or classification FKs.

    This is a schema check — if the columns exist, the invariant is violated.
    Returns:
      {"status": "ok"} — columns do not exist
      {"status": "violated", "forbidden_columns": [...]} — CRITICAL
    """
    result = db.execute(text(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'kb_guidance_traces'
          AND column_name IN ('chunk_id', 'classification_result_id')
        """
    )).fetchall()

    forbidden = [row[0] for row in result]
    if not forbidden:
        return {"status": "ok"}
    return {
        "status": "violated",
        "forbidden_columns": forbidden,
        "message": (
            "CRITICAL: kb_guidance_traces contains forbidden FK columns. "
            "Schema integrity violated."
        ),
    }


def check_cross_firm_kb_access(db: Session, firm_id: str) -> dict:
    """Verify all KB chunks for this firm are isolated to this firm.

    Returns count of kb_chunks where firm_id does not match kb_document.firm_id.
    Must always return 0.
    """
    result = db.execute(text(
        """
        SELECT COUNT(*) FROM kb_chunks kc
        JOIN kb_documents kd ON kd.id = kc.kb_document_id
        WHERE kc.firm_id != kd.firm_id
          AND (kc.firm_id = :firm_id OR kd.firm_id = :firm_id)
        """
    ), {"firm_id": firm_id}).scalar()

    count = int(result or 0)
    if count == 0:
        return {"status": "ok", "violation_count": 0}
    return {
        "status": "violated",
        "violation_count": count,
        "message": "CRITICAL: KB chunk firm_id does not match parent document firm_id.",
    }
