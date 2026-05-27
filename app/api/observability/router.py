"""Operational visibility endpoints — workflow state, invariants, queue health."""
import logging
from datetime import datetime
from typing import Literal

from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api.kb.invariants import (
    check_cross_firm_kb_access,
    check_kb_guidance_trace_isolation,
    check_provenance_separation,
)
from app.api.review.router import (
    _active_sections_by_code,
    _compute_export_eligible,
    _latest_review,
)
from app.core.auth import TokenClaims, get_current_claims, require_case_access
from app.core.database import get_db
from app.core.models import (
    Case,
    Document,
    DocumentVersion,
    DraftOutput,
    DraftSection,
    KBChunk,
    KBDocument,
)
from app.workers.enqueue import get_arq_pool, replay_failed_job
from app.workers.settings import REDIS_SETTINGS


logger = logging.getLogger(__name__)

router = APIRouter(tags=["observability"])

QUEUE_NAME = "llm_tasks"


class ReplayRequest(BaseModel):
    task_name: Literal[
        "ingest_document",
        "ingest_kb_document",
        "classify_document_version",
    ]
    kwargs: dict


def _check_orphaned_generation_traces(db: Session) -> dict:
    result = db.execute(text(
        """
        SELECT COUNT(*) FROM generation_traces gt
        WHERE NOT EXISTS (
            SELECT 1 FROM draft_sections ds WHERE ds.id = gt.draft_section_id
        )
        """
    )).scalar()
    count = int(result or 0)
    if count == 0:
        return {"status": "ok", "violation_count": 0}
    return {
        "status": "violated",
        "violation_count": count,
        "message": "CRITICAL: generation_traces reference missing draft_sections.",
    }


def _check_null_review_snapshots(db: Session, firm_id: str) -> dict:
    result = db.execute(text(
        """
        SELECT COUNT(*) FROM draft_exports
        WHERE review_snapshot IS NULL
          AND firm_id = :firm_id
        """
    ), {"firm_id": firm_id}).scalar()
    count = int(result or 0)
    if count == 0:
        return {"status": "ok", "violation_count": 0}
    return {
        "status": "violated",
        "violation_count": count,
        "message": "CRITICAL: draft_exports rows with null review_snapshot.",
    }


def _draft_review_counts(db: Session, draft_id: str) -> tuple[int, int, int]:
    active = _active_sections_by_code(db, draft_id)
    approved = 0
    rejected = 0
    pending = 0
    for section in active.values():
        review = _latest_review(db, section.id)
        if review is None:
            pending += 1
        elif review.action in ("approved", "edited"):
            approved += 1
        elif review.action == "rejected":
            rejected += 1
        else:
            pending += 1
    return approved, rejected, pending


@router.get("/observability/workflow/{case_id}")
def get_workflow_state(
    *,
    case_id: str = Depends(require_case_access),
    db: Session = Depends(get_db),
):
    """Return full workflow state for a case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    documents = (
        db.query(Document)
        .filter(Document.case_id == case_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    document_rows = []
    for doc in documents:
        version_count = (
            db.query(func.count(DocumentVersion.id))
            .filter(DocumentVersion.document_id == doc.id)
            .scalar()
        ) or 0
        latest_version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        document_rows.append(
            {
                "document_id": doc.id,
                "name": doc.original_name,
                "lifecycle_state": doc.lifecycle_state,
                "version_count": version_count,
                "latest_extraction_status": (
                    latest_version.extraction_status if latest_version else None
                ),
            }
        )

    drafts = (
        db.query(DraftOutput)
        .filter(DraftOutput.case_id == case_id)
        .order_by(DraftOutput.created_at.desc())
        .all()
    )
    draft_rows = []
    for draft in drafts:
        section_count = (
            db.query(func.count(DraftSection.id))
            .filter(DraftSection.draft_output_id == draft.id)
            .scalar()
        ) or 0
        approved, rejected, pending = _draft_review_counts(db, draft.id)
        draft_rows.append(
            {
                "draft_id": draft.id,
                "overall_status": draft.overall_status,
                "section_count": section_count,
                "sections_approved": approved,
                "sections_rejected": rejected,
                "sections_pending": pending,
                "export_eligible": _compute_export_eligible(db, draft.id),
                "created_at": draft.created_at.isoformat(),
            }
        )

    kb_documents = (
        db.query(KBDocument)
        .filter(KBDocument.firm_id == case.firm_id)
        .order_by(KBDocument.created_at.desc())
        .all()
    )
    kb_rows = []
    for kb_doc in kb_documents:
        chunk_count = (
            db.query(func.count(KBChunk.id))
            .filter(KBChunk.kb_document_id == kb_doc.id)
            .scalar()
        ) or 0
        kb_rows.append(
            {
                "kb_document_id": kb_doc.id,
                "title": kb_doc.title,
                "lifecycle_state": kb_doc.lifecycle_state,
                "chunk_count": chunk_count,
            }
        )

    return {
        "case_id": case_id,
        "documents": document_rows,
        "drafts": draft_rows,
        "kb_documents": kb_rows,
    }


@router.get("/observability/invariants")
def get_observability_invariants(
    *,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Run all provenance and structural invariant checks."""
    return {
        "firm_id": claims.firm_id,
        "checks": {
            "provenance_separation": check_provenance_separation(db),
            "kb_guidance_trace_isolation": check_kb_guidance_trace_isolation(db),
            "cross_firm_kb_access": check_cross_firm_kb_access(db, claims.firm_id),
            "orphaned_generation_traces": _check_orphaned_generation_traces(db),
            "null_review_snapshots": _check_null_review_snapshots(db, claims.firm_id),
        },
    }


@router.get("/observability/queue-health")
async def get_queue_health():
    """Return ARQ Redis queue state. Never raises 503 on Redis failure."""
    try:
        pool = await create_pool(REDIS_SETTINGS)
        try:
            queued_jobs = int(await pool.zcard(QUEUE_NAME) or 0)
            failed_jobs = 0
            try:
                results = await pool.all_job_results()
                failed_jobs = sum(1 for result in results if not result.success)
            except Exception:
                logger.exception("Failed to read ARQ job results for queue health")
            return {
                "redis_connected": True,
                "queue_name": QUEUE_NAME,
                "queued_jobs": queued_jobs,
                "failed_jobs": failed_jobs,
            }
        finally:
            await pool.aclose()
    except Exception:
        logger.exception("Redis unreachable for queue health check")
        return {"redis_connected": False}


@router.get("/observability/failed-lifecycles")
def get_failed_lifecycles(
    *,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Return firm-scoped documents and KB documents stuck in non-terminal states."""
    stuck_documents = db.execute(
        text(
            """
            SELECT d.id, d.original_name, d.lifecycle_state, d.created_at
            FROM documents d
            JOIN cases c ON c.id = d.case_id
            WHERE c.firm_id = :firm_id
              AND d.lifecycle_state NOT IN ('indexed', 'final')
              AND d.created_at < now() - interval '1 hour'
            ORDER BY d.created_at ASC
            """
        ),
        {"firm_id": claims.firm_id},
    ).fetchall()

    stuck_kb_documents = db.execute(
        text(
            """
            SELECT id, title, lifecycle_state, created_at
            FROM kb_documents
            WHERE firm_id = :firm_id
              AND lifecycle_state NOT IN ('indexed')
              AND created_at < now() - interval '1 hour'
            ORDER BY created_at ASC
            """
        ),
        {"firm_id": claims.firm_id},
    ).fetchall()

    return {
        "stuck_documents": [
            {
                "document_id": row[0],
                "name": row[1],
                "lifecycle_state": row[2],
                "created_at": row[3].isoformat(),
            }
            for row in stuck_documents
        ],
        "stuck_kb_documents": [
            {
                "kb_document_id": row[0],
                "title": row[1],
                "lifecycle_state": row[2],
                "created_at": row[3].isoformat(),
            }
            for row in stuck_kb_documents
        ],
    }


@router.post("/observability/replay", status_code=202)
async def replay_task(
    *,
    body: ReplayRequest,
    claims: TokenClaims = Depends(get_current_claims),
):
    """Re-enqueue a failed task with firm-validated kwargs."""
    firm_id = body.kwargs.get("firm_id")
    if not firm_id:
        raise HTTPException(status_code=403, detail="firm_id required in kwargs")
    if firm_id != claims.firm_id:
        raise HTTPException(status_code=403, detail="firm_id mismatch")

    pool = await get_arq_pool()
    try:
        job_id = await replay_failed_job(
            pool,
            task_name=body.task_name,
            kwargs=body.kwargs,
        )
    finally:
        await pool.aclose()

    return {
        "job_id": job_id,
        "task_name": body.task_name,
        "queued_at": datetime.utcnow().isoformat(),
    }
