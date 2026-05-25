"""Processing event writer. Best-effort: never raises."""
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.models import ProcessingEvent


logger = logging.getLogger(__name__)


def write_event(
    db: Session,
    event_type: str,
    status: str,
    case_id: str,
    document_id: Optional[str] = None,
    document_version_id: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> None:
    """Persist a `ProcessingEvent` row.

    Failures (DB or otherwise) are logged and swallowed; this function never
    raises. The session is rolled back if the commit fails so the caller's
    next operation starts from a clean transactional state.
    """
    try:
        event = ProcessingEvent(
            case_id=case_id,
            document_id=document_id,
            document_version_id=document_version_id,
            event_type=event_type,
            status=status,
            detail=detail,
            error_message=error_message,
        )
        db.add(event)
        db.commit()
    except Exception:
        logger.exception(
            "Failed to write processing event "
            "(event_type=%s, status=%s, case_id=%s, document_id=%s, document_version_id=%s)",
            event_type,
            status,
            case_id,
            document_id,
            document_version_id,
        )
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after failed event write also failed")
