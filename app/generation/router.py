"""Generation endpoints.

POST /cases/{case_id}/generate
GET  /cases/{case_id}/drafts
GET  /cases/{case_id}/drafts/{draft_id}
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_case_access
from app.core.database import get_db
from app.core.models import DraftOutput, DraftSection, GenerationTrace
from app.generation.service import generate_draft


logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])


class GenerateRequest(BaseModel):
    document_id: str
    version_id: str
    visa_type: Literal["EB1", "EB2"]
    force_generate: bool = False


@router.post("/cases/{case_id}/generate", status_code=202)
def generate_draft_endpoint(
    *,
    case_id: str = Depends(require_case_access),
    body: GenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a section-based legal draft for a case."""
    result = generate_draft(
        db,
        case_id,
        body.document_id,
        body.version_id,
        body.visa_type,
        body.force_generate,
    )
    status_val = result["status"]

    if status_val == "ok":
        draft = (
            db.query(DraftOutput)
            .filter(DraftOutput.id == result["draft_id"])
            .first()
        )
        return {
            "draft_id": result["draft_id"],
            "case_id": case_id,
            "visa_type": body.visa_type,
            "overall_status": result["overall_status"],
            "coverage_summary": result["coverage_summary"],
            "sections": result["sections"],
            "created_at": draft.created_at.isoformat() if draft else None,
        }
    if status_val == "coverage_blocked":
        raise HTTPException(
            status_code=422,
            detail={
                "status": "coverage_incomplete",
                "missing_criteria": result["missing_criteria"],
                "insufficient_criteria": result.get("insufficient_criteria", []),
                "override_available": result["override_available"],
            },
        )
    if status_val == "not_found":
        raise HTTPException(
            status_code=404, detail="Document version not found"
        )
    if status_val == "failed":
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Generation failed"),
        )

    logger.error("Unexpected status from generate_draft: %r", status_val)
    raise HTTPException(status_code=500, detail="Internal error")


@router.get("/cases/{case_id}/drafts")
def list_drafts(
    *,
    case_id: str = Depends(require_case_access),
    db: Session = Depends(get_db),
):
    """List draft outputs for a case, newest first."""
    drafts = (
        db.query(DraftOutput)
        .filter(DraftOutput.case_id == case_id)
        .order_by(DraftOutput.created_at.desc())
        .all()
    )

    return {
        "case_id": case_id,
        "drafts": [
            {
                "id": draft.id,
                "visa_type": draft.visa_type,
                "overall_status": draft.overall_status,
                "section_count": db.query(DraftSection)
                .filter(DraftSection.draft_output_id == draft.id)
                .count(),
                "created_at": draft.created_at.isoformat(),
            }
            for draft in drafts
        ],
    }


@router.get("/cases/{case_id}/drafts/{draft_id}")
def get_draft(
    *,
    case_id: str = Depends(require_case_access),
    draft_id: str,
    db: Session = Depends(get_db),
):
    """Fetch a single draft with sections and generation traces."""
    draft = (
        db.query(DraftOutput)
        .filter(DraftOutput.id == draft_id, DraftOutput.case_id == case_id)
        .first()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    sections = (
        db.query(DraftSection)
        .filter(DraftSection.draft_output_id == draft.id)
        .order_by(DraftSection.created_at.asc())
        .all()
    )

    return {
        "id": draft.id,
        "case_id": draft.case_id,
        "visa_type": draft.visa_type,
        "overall_status": draft.overall_status,
        "coverage_summary": draft.coverage_summary,
        "sections": [
            {
                "id": section.id,
                "section_code": section.section_code,
                "content": section.content,
                "prompt_template_id": section.prompt_template_id,
                "tokens_used": section.tokens_used,
                "created_at": section.created_at.isoformat(),
                "traces": [
                    {
                        "chunk_id": trace.chunk_id,
                        "classification_result_id": trace.classification_result_id,
                        "citation_text": trace.citation_text,
                        "similarity_score": trace.similarity_score,
                    }
                    for trace in db.query(GenerationTrace)
                    .filter(GenerationTrace.draft_section_id == section.id)
                    .all()
                ],
            }
            for section in sections
        ],
        "created_at": draft.created_at.isoformat(),
    }
