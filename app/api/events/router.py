"""Case-level processing-event endpoints.

GET /cases/{case_id}/events
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import require_case_access
from app.core.database import get_db
from app.core.models import ProcessingEvent
from app.core.schemas import CaseEventListPaginated, ProcessingEventDetail


router = APIRouter(tags=["events"])


# ---------------------------------------------------------------------------
# CANONICAL EVENT-TYPE REGISTRY
# ---------------------------------------------------------------------------
# This set is the single source of truth for valid `event_type` filter values
# on `GET /cases/{case_id}/events`.
#
# If you add a new producer (or a new event_type string in an existing
# producer) anywhere in `app/ingestion/`, `app/retrieval/`, or elsewhere in
# the API layer, ADD THE STRING HERE. Otherwise the API will accept the event
# row but reject filter queries for that type with 422.
# ---------------------------------------------------------------------------
ALLOWED_EVENT_TYPES = {
    "document_received",
    "s3_upload_started",
    "s3_upload_completed",
    "s3_upload_failed",
    "text_extraction_started",
    "text_extraction_completed",
    "text_extraction_failed",
    "chunking_completed",
    "chunking_failed",
    "embedding_completed",
    "embedding_failed",
    "classification_completed",
    "classification_failed",
    "generation_completed",
    "generation_failed",
}


@router.get("/cases/{case_id}/events", response_model=CaseEventListPaginated)
def list_case_events(
    *,
    case_id: str = Depends(require_case_access),
    event_type: Optional[str] = Query(default=None),
    before: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> CaseEventListPaginated:
    """List processing events for a case, oldest first.

    Optional `event_type` query parameter filters to a single event type. The
    value must be one of `ALLOWED_EVENT_TYPES`; anything else returns 422.
    An empty result set returns 200 with `events: []` — never 404.
    """
    if event_type is not None and event_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid event_type. Allowed values: {sorted(ALLOWED_EVENT_TYPES)}"
            ),
        )

    query = db.query(ProcessingEvent).filter(ProcessingEvent.case_id == case_id)
    if event_type is not None:
        query = query.filter(ProcessingEvent.event_type == event_type)

    if before is not None:
        try:
            before_dt = datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid before cursor — must be ISO datetime string",
            )
        query = query.filter(ProcessingEvent.created_at < before_dt)

    events = (
        query.order_by(ProcessingEvent.created_at.asc()).limit(limit).all()
    )

    next_cursor = (
        events[-1].created_at.isoformat() if len(events) == limit else None
    )

    return CaseEventListPaginated(
        case_id=case_id,
        events=[ProcessingEventDetail.model_validate(e) for e in events],
        next_cursor=next_cursor,
        limit=limit,
    )
