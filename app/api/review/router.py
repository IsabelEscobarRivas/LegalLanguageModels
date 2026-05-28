"""Review workflow endpoints — approve, reject, edit, regenerate, export."""
import logging
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import TokenClaims, get_current_claims, require_case_access
from app.core.database import get_db
from app.core.models import (
    Case,
    DraftExport,
    DraftOutput,
    DraftSection,
    DraftSectionReview,
    GenerationTrace,
)
from app.generation.service import SECTION_ORDER, _generate_section


logger = logging.getLogger(__name__)

router = APIRouter(tags=["review"])


class ReviewRequest(BaseModel):
    action: Literal["approved", "rejected", "edited"]
    reviewer_edit: Optional[str] = None
    reviewer_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    regeneration_requested: bool = False


class RegenerateRequest(BaseModel):
    visa_type: Literal["EB1", "EB2"]
    force_generate: bool = True


class ExportRequest(BaseModel):
    export_format: Literal["json", "txt"]


def _get_draft(db: Session, case_id: str, draft_id: str) -> DraftOutput | None:
    return (
        db.query(DraftOutput)
        .filter(DraftOutput.id == draft_id, DraftOutput.case_id == case_id)
        .first()
    )


def _get_section(db: Session, draft_id: str, section_id: str) -> DraftSection | None:
    return (
        db.query(DraftSection)
        .filter(
            DraftSection.id == section_id,
            DraftSection.draft_output_id == draft_id,
        )
        .first()
    )


def _active_sections_by_code(db: Session, draft_id: str) -> dict[str, DraftSection]:
    """Latest DraftSection row per section_code (handles regenerations)."""
    sections = (
        db.query(DraftSection)
        .filter(DraftSection.draft_output_id == draft_id)
        .order_by(DraftSection.created_at.asc())
        .all()
    )
    active: dict[str, DraftSection] = {}
    for section in sections:
        active[section.section_code] = section
    return active


def _latest_review(db: Session, section_id: str) -> DraftSectionReview | None:
    return (
        db.query(DraftSectionReview)
        .filter(DraftSectionReview.draft_section_id == section_id)
        .order_by(DraftSectionReview.created_at.desc())
        .first()
    )


def _section_review_summary(
    db: Session,
    section: DraftSection,
) -> dict:
    review = _latest_review(db, section.id)
    return {
        "section_id": section.id,
        "section_code": section.section_code,
        "latest_action": review.action if review else None,
        "reviewer_edit": review.reviewer_edit if review else None,
        "regeneration_requested": review.regeneration_requested if review else False,
        "review_count": (
            db.query(DraftSectionReview)
            .filter(DraftSectionReview.draft_section_id == section.id)
            .count()
        ),
    }


def _compute_export_eligible(db: Session, draft_id: str) -> bool:
    active = _active_sections_by_code(db, draft_id)
    if not active:
        return False

    for section in active.values():
        review = _latest_review(db, section.id)
        if review is None:
            return False
        if review.action == "rejected" and not review.regenerated_section_id:
            return False
        if review.action not in ("approved", "edited"):
            return False
    return True


def _provenance_type(db: Session, section: DraftSection, review: DraftSectionReview) -> str:
    if review.action == "edited":
        return "ATTORNEY_EDITED"
    regenerated = (
        db.query(DraftSectionReview)
        .filter(DraftSectionReview.regenerated_section_id == section.id)
        .first()
    )
    if regenerated is not None:
        return "REGENERATED"
    return "AI_GENERATED"


def _section_traces(db: Session, section_id: str) -> list[dict]:
    return [
        {
            "chunk_id": trace.chunk_id,
            "classification_result_id": trace.classification_result_id,
            "citation_text": trace.citation_text,
            "similarity_score": trace.similarity_score,
        }
        for trace in db.query(GenerationTrace)
        .filter(GenerationTrace.draft_section_id == section_id)
        .all()
    ]


@router.post(
    "/cases/{case_id}/drafts/{draft_id}/sections/{section_id}/review",
    status_code=201,
)
def submit_section_review(
    *,
    case_id: str = Depends(require_case_access),
    draft_id: str,
    section_id: str,
    body: ReviewRequest,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Record an attorney review action for a draft section."""
    draft = _get_draft(db, case_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    section = _get_section(db, draft_id, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    if body.action == "edited":
        if not body.reviewer_edit or not body.reviewer_edit.strip():
            raise HTTPException(
                status_code=422,
                detail="reviewer_edit is required when action is edited",
            )
    elif body.action == "approved":
        if body.reviewer_edit is not None:
            raise HTTPException(
                status_code=422,
                detail="reviewer_edit must be null when action is approved",
            )

    review = DraftSectionReview(
        id=str(uuid.uuid4()),
        draft_section_id=section_id,
        case_id=case_id,
        firm_id=claims.firm_id,
        reviewer_id=claims.sub,
        action=body.action,
        reviewer_edit=body.reviewer_edit.strip() if body.reviewer_edit else None,
        reviewer_notes=body.reviewer_notes.strip() if body.reviewer_notes else None,
        rejection_reason=body.rejection_reason,
        regeneration_requested=body.regeneration_requested,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "review_id": review.id,
        "draft_section_id": section_id,
        "action": review.action,
        "created_at": review.created_at.isoformat(),
    }


@router.get("/cases/{case_id}/drafts/{draft_id}/sections/{section_id}/reviews")
def list_section_reviews(
    *,
    case_id: str = Depends(require_case_access),
    draft_id: str,
    section_id: str,
    db: Session = Depends(get_db),
):
    """List all review rows for a section, newest first."""
    draft = _get_draft(db, case_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    section = _get_section(db, draft_id, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    reviews = (
        db.query(DraftSectionReview)
        .filter(DraftSectionReview.draft_section_id == section_id)
        .order_by(DraftSectionReview.created_at.desc())
        .all()
    )

    return {
        "draft_section_id": section_id,
        "reviews": [
            {
                "id": r.id,
                "action": r.action,
                "reviewer_id": r.reviewer_id,
                "reviewer_edit": r.reviewer_edit,
                "rejection_reason": r.rejection_reason,
                "regeneration_requested": r.regeneration_requested,
                "regenerated_section_id": r.regenerated_section_id,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }


@router.get("/cases/{case_id}/drafts/{draft_id}/review-status")
def get_review_status(
    *,
    case_id: str = Depends(require_case_access),
    draft_id: str,
    db: Session = Depends(get_db),
):
    """Summarize per-section review state and export eligibility."""
    draft = _get_draft(db, case_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    active = _active_sections_by_code(db, draft_id)
    sections = [_section_review_summary(db, s) for s in active.values()]
    sections.sort(key=lambda s: SECTION_ORDER.index(s["section_code"]))

    return {
        "draft_id": draft_id,
        "sections": sections,
        "export_eligible": _compute_export_eligible(db, draft_id),
    }


@router.post(
    "/cases/{case_id}/drafts/{draft_id}/sections/{section_id}/regenerate",
    status_code=201,
)
def regenerate_section(
    *,
    case_id: str = Depends(require_case_access),
    draft_id: str,
    section_id: str,
    body: RegenerateRequest,
    db: Session = Depends(get_db),
):
    """Regenerate a rejected section and link the new section to the review row."""
    draft = _get_draft(db, case_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    section = _get_section(db, draft_id, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    review = _latest_review(db, section_id)
    if review is None or review.action != "rejected":
        raise HTTPException(
            status_code=422,
            detail="Latest review must be rejected before regeneration",
        )
    if not review.regeneration_requested:
        raise HTTPException(
            status_code=422,
            detail="regeneration_requested must be true on the rejection review",
        )

    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    active = _active_sections_by_code(db, draft_id)
    prior_sections = []
    for code in SECTION_ORDER:
        if code == section.section_code:
            break
        if code in active:
            prior_sections.append(
                {
                    "section_code": code,
                    "content": active[code].content,
                }
            )

    section_result = _generate_section(
        db=db,
        draft_output_id=draft_id,
        case_id=case_id,
        version_id=draft.document_version_id,
        visa_type=body.visa_type,
        section_code=section.section_code,
        firm_id=case.firm_id,
        coverage_summary=draft.coverage_summary,
        prior_sections=prior_sections,
    )
    if section_result is None:
        raise HTTPException(status_code=503, detail="Section regeneration failed")

    new_section = (
        db.query(DraftSection)
        .filter(
            DraftSection.draft_output_id == draft_id,
            DraftSection.section_code == section.section_code,
        )
        .order_by(DraftSection.created_at.desc())
        .first()
    )
    if new_section is None:
        raise HTTPException(status_code=500, detail="Regenerated section not found")

    review.regenerated_section_id = new_section.id
    db.commit()

    return {
        "original_section_id": section_id,
        "regenerated_section_id": new_section.id,
        "section_code": new_section.section_code,
        "content": new_section.content,
        "traces": _section_traces(db, new_section.id),
    }


@router.post("/cases/{case_id}/drafts/{draft_id}/export", status_code=201)
def export_draft(
    *,
    case_id: str = Depends(require_case_access),
    draft_id: str,
    body: ExportRequest,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Export an approved draft as an immutable snapshot."""
    draft = _get_draft(db, case_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if not _compute_export_eligible(db, draft_id):
        raise HTTPException(
            status_code=422,
            detail="All sections must be approved or edited before export",
        )

    active = _active_sections_by_code(db, draft_id)
    section_snapshot: dict = {"sections": []}
    review_snapshot: dict = {"sections": []}

    for code in SECTION_ORDER:
        if code not in active:
            continue
        section = active[code]
        review = _latest_review(db, section.id)
        if review is None:
            raise HTTPException(status_code=422, detail="Missing review for section")

        if review.action == "edited":
            content = review.reviewer_edit or section.content
        else:
            content = section.content

        provenance_type = _provenance_type(db, section, review)
        section_snapshot["sections"].append(
            {
                "section_code": code,
                "section_id": section.id,
                "content": content,
                "provenance_type": provenance_type,
                "generated_content": section.content,
            }
        )
        review_snapshot["sections"].append(
            {
                "section_id": section.id,
                "section_code": code,
                "action": review.action,
                "reviewer_id": review.reviewer_id,
                "reviewer_edit": review.reviewer_edit,
                "provenance_type": provenance_type,
                "created_at": review.created_at.isoformat(),
            }
        )

    export_row = DraftExport(
        id=str(uuid.uuid4()),
        draft_output_id=draft_id,
        case_id=case_id,
        firm_id=claims.firm_id,
        exported_by=claims.sub,
        export_format=body.export_format,
        section_snapshot=section_snapshot,
        review_snapshot=review_snapshot,
    )
    db.add(export_row)
    db.commit()
    db.refresh(export_row)

    if body.export_format == "txt":
        lines: list[str] = []
        for entry in section_snapshot["sections"]:
            title = entry["section_code"].replace("_", " ").title()
            lines.append(f"=== {title} ===")
            lines.append(entry["content"])
            lines.append("")
        content: str | dict = "\n".join(lines).rstrip() + "\n"
    else:
        content = {
            "draft_id": draft_id,
            "case_id": case_id,
            "exported_by": claims.sub,
            "sections": section_snapshot["sections"],
            "review_metadata": review_snapshot,
        }

    return {
        "export_id": export_row.id,
        "export_format": body.export_format,
        "content": content,
        "created_at": export_row.created_at.isoformat(),
    }


@router.get("/cases/{case_id}/drafts/{draft_id}/exports")
def list_exports(
    *,
    case_id: str = Depends(require_case_access),
    draft_id: str,
    db: Session = Depends(get_db),
):
    """List export records for a draft (metadata only)."""
    draft = _get_draft(db, case_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    exports = (
        db.query(DraftExport)
        .filter(
            DraftExport.draft_output_id == draft_id,
            DraftExport.case_id == case_id,
        )
        .order_by(DraftExport.created_at.desc())
        .all()
    )

    return {
        "draft_id": draft_id,
        "exports": [
            {
                "id": row.id,
                "export_format": row.export_format,
                "exported_by": row.exported_by,
                "s3_export_key": row.s3_export_key,
                "created_at": row.created_at.isoformat(),
            }
            for row in exports
        ],
    }
