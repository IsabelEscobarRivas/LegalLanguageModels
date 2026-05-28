"""Classification endpoints.

POST /cases/{case_id}/chunks/{chunk_id}/classify
POST /cases/{case_id}/classify-version
POST /cases/{case_id}/classifications/{classification_result_id}/feedback
GET  /cases/{case_id}/classifications/{classification_result_id}/feedback
GET  /cases/{case_id}/chunks/{chunk_id}/effective-classification
GET  /cases/{case_id}/coverage
"""
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.classification.classifier import (
    classify_chunk,
    classify_document_version,
)
from app.classification.coverage import evaluate_coverage
from app.classification.feedback import submit_feedback
from app.classification.resolver import resolve_effective_classification
from app.ingestion.chunker import chunk_document_version
from app.core.auth import TokenClaims, get_current_claims, require_case_access
from app.core.database import get_db
from app.core.models import (
    Chunk,
    ClassificationFeedback,
    ClassificationResult,
    CriteriaReference,
    Document,
    DocumentVersion,
    SectionAffinityReference,
)
from app.core.schemas import (
    ClassificationFeedbackRequest,
    ClassificationFeedbackResponse,
    CoverageResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["classification"])


class ClassifyChunkRequest(BaseModel):
    visa_type: Literal["EB1", "EB2"]
    force_reclassify: bool = False


class ClassifyVersionRequest(BaseModel):
    document_id: str
    version_id: str
    visa_type: Literal["EB1", "EB2"]
    force_reclassify: bool = False


@router.post(
    "/cases/{case_id}/chunks/{chunk_id}/classify",
    status_code=202,
)
def trigger_chunk_classification(
    *,
    case_id: str = Depends(require_case_access),
    chunk_id: str,
    body: ClassifyChunkRequest,
    db: Session = Depends(get_db),
):
    """Classify a single chunk against active USCIS criteria."""
    result = classify_chunk(
        db,
        case_id,
        chunk_id,
        body.visa_type,
        force_reclassify=body.force_reclassify,
    )
    status_val = result["status"]

    if status_val == "ok":
        return {
            "chunk_id": result["chunk_id"],
            "classifications_created": result["classifications_created"],
            "classifications": result["classifications"],
        }
    if status_val == "exists":
        classifications = result["classifications"]
        return JSONResponse(
            status_code=200,
            content={
                "chunk_id": chunk_id,
                "classifications_created": len(classifications),
                "classifications": classifications,
            },
        )
    if status_val == "not_found":
        raise HTTPException(status_code=404, detail="Chunk not found")
    if status_val == "failed":
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Classification failed"),
        )

    logger.error(
        "Unexpected status from classify_chunk: %r", status_val
    )
    raise HTTPException(status_code=500, detail="Internal error")


@router.post(
    "/cases/{case_id}/classify-version",
    status_code=202,
)
def trigger_version_classification(
    *,
    case_id: str = Depends(require_case_access),
    body: ClassifyVersionRequest,
    db: Session = Depends(get_db),
):
    """Classify all chunks for a document version.

    UI uploads produce an extracted DocumentVersion first. If no chunks exist
    yet, create them on demand so the attorney-facing Classify action works as
    the next step after upload.
    """
    result = classify_document_version(
        db,
        case_id,
        body.document_id,
        body.version_id,
        body.visa_type,
        force_reclassify=body.force_reclassify,
    )
    if result.get("status") == "failed" and result.get("reason") == "no_chunks":
        chunk_result = chunk_document_version(
            db,
            case_id,
            body.document_id,
            body.version_id,
            strategy="paragraph",
        )
        if chunk_result["status"] not in ("ok", "exists"):
            raise HTTPException(
                status_code=503,
                detail="chunking: " + chunk_result.get("reason", "failed"),
            )
        result = classify_document_version(
            db,
            case_id,
            body.document_id,
            body.version_id,
            body.visa_type,
            force_reclassify=body.force_reclassify,
        )
    status_val = result["status"]

    if status_val == "ok":
        return {
            "version_id": result["version_id"],
            "chunks_processed": result["chunks_processed"],
            "classifications_created": result["classifications_created"],
            "chunks_with_no_match": result["chunks_with_no_match"],
            "chunks_failed": result["chunks_failed"],
        }
    if status_val == "not_found":
        raise HTTPException(status_code=404, detail="Version not found")
    if status_val == "failed":
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Classification failed"),
        )

    logger.error(
        "Unexpected status from classify_document_version: %r", status_val
    )
    raise HTTPException(status_code=500, detail="Internal error")


@router.post(
    "/cases/{case_id}/classifications/{classification_result_id}/feedback",
    response_model=ClassificationFeedbackResponse,
    status_code=201,
)
def submit_classification_feedback(
    *,
    case_id: str = Depends(require_case_access),
    classification_result_id: str,
    body: ClassificationFeedbackRequest,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> ClassificationFeedbackResponse:
    """Submit human feedback on a classification result."""
    result = submit_feedback(
        db,
        case_id,
        classification_result_id,
        reviewer_id=claims.sub,
        action=body.action,
        corrected_criteria_id=body.corrected_criteria_id,
        corrected_section_affinity_id=body.corrected_section_affinity_id,
        corrected_confidence_score=body.corrected_confidence_score,
        rationale=body.rationale,
    )
    status_val = result["status"]

    if status_val == "ok":
        return ClassificationFeedbackResponse(
            id=result["id"],
            classification_result_id=result["classification_result_id"],
            action=result["action"],
            created_at=datetime.fromisoformat(result["created_at"]),
        )
    if status_val == "not_found":
        raise HTTPException(
            status_code=404, detail="Classification result not found"
        )
    if status_val == "invalid":
        raise HTTPException(status_code=422, detail=result["reason"])
    if status_val == "failed":
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Feedback submission failed"),
        )

    logger.error("Unexpected status from submit_feedback: %r", status_val)
    raise HTTPException(status_code=500, detail="Internal error")


@router.get(
    "/cases/{case_id}/classifications/{classification_result_id}/feedback",
)
def get_classification_feedback(
    *,
    case_id: str = Depends(require_case_access),
    classification_result_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve all feedback rows for a classification result."""
    result_row = (
        db.query(ClassificationResult)
        .filter(
            ClassificationResult.id == classification_result_id,
            ClassificationResult.case_id == case_id,
        )
        .first()
    )
    if result_row is None:
        raise HTTPException(
            status_code=404, detail="Classification result not found"
        )

    feedback_rows = (
        db.query(ClassificationFeedback)
        .filter(
            ClassificationFeedback.classification_result_id
            == classification_result_id
        )
        .order_by(ClassificationFeedback.created_at.desc())
        .all()
    )

    return {
        "classification_result_id": classification_result_id,
        "feedback": [
            {
                "id": row.id,
                "action": row.action,
                "corrected_criteria_id": row.corrected_criteria_id,
                "corrected_section_affinity_id": row.corrected_section_affinity_id,
                "corrected_confidence_score": row.corrected_confidence_score,
                "rationale": row.rationale,
                "reviewer_id": row.reviewer_id,
                "created_at": row.created_at.isoformat(),
            }
            for row in feedback_rows
        ],
    }


@router.get("/cases/{case_id}/chunks/{chunk_id}/effective-classification")
def get_effective_classification(
    *,
    case_id: str = Depends(require_case_access),
    chunk_id: str,
    db: Session = Depends(get_db),
):
    """Return the effective classification for a chunk, applying latest override."""
    chunk = (
        db.query(Chunk)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .join(Document, Document.id == DocumentVersion.document_id)
        .filter(Chunk.id == chunk_id, Document.case_id == case_id)
        .first()
    )
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    classification_results = (
        db.query(ClassificationResult)
        .filter(
            ClassificationResult.chunk_id == chunk_id,
            ClassificationResult.case_id == case_id,
        )
        .all()
    )
    if not classification_results:
        raise HTTPException(
            status_code=404, detail="Classification result not found"
        )

    result_ids = [row.id for row in classification_results]
    latest_feedback = (
        db.query(ClassificationFeedback)
        .filter(
            ClassificationFeedback.classification_result_id.in_(result_ids),
            ClassificationFeedback.action.in_(
                ["confirmed", "corrected", "rejected"]
            ),
        )
        .order_by(ClassificationFeedback.created_at.desc())
        .first()
    )

    if latest_feedback is not None:
        target_result_id = latest_feedback.classification_result_id
    else:
        target_result_id = max(
            classification_results, key=lambda row: row.confidence_score
        ).id

    resolved = resolve_effective_classification(db, target_result_id)
    if resolved["status"] == "not_found":
        raise HTTPException(
            status_code=404, detail="Classification result not found"
        )

    if resolved.get("excluded"):
        return {
            "excluded": True,
            "reason": resolved.get("reason", "reviewer_rejected"),
        }

    criteria = (
        db.query(CriteriaReference)
        .filter(CriteriaReference.id == resolved["criteria_id"])
        .first()
    )
    section = (
        db.query(SectionAffinityReference)
        .filter(SectionAffinityReference.id == resolved["section_affinity_id"])
        .first()
    )

    return {
        "chunk_id": chunk_id,
        "classification_result_id": target_result_id,
        "criteria_id": resolved["criteria_id"],
        "criteria_code": criteria.code if criteria else "",
        "section_affinity_id": resolved["section_affinity_id"],
        "section_affinity_code": section.code if section else "",
        "confidence_score": resolved["confidence_score"],
        "override_applied": resolved["override_applied"],
        "feedback_id": resolved["feedback_id"],
        "excluded": False,
    }


@router.get(
    "/cases/{case_id}/coverage",
    response_model=CoverageResponse,
)
def get_coverage(
    *,
    case_id: str = Depends(require_case_access),
    visa_type: str = Query(...),
    db: Session = Depends(get_db),
) -> CoverageResponse:
    """Evaluate USCIS criteria coverage for a case."""
    if visa_type not in ("EB1", "EB2"):
        raise HTTPException(status_code=422, detail="Invalid visa_type")

    result = evaluate_coverage(db, case_id, visa_type)
    status_val = result["status"]

    if status_val == "ok":
        return CoverageResponse(
            case_id=result["case_id"],
            visa_type=result["visa_type"],
            overall_status=result["overall_status"],
            evaluated_at=result["evaluated_at"],
            coverage=result["coverage"],
        )
    if status_val == "failed":
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Coverage evaluation failed"),
        )

    logger.error("Unexpected status from evaluate_coverage: %r", status_val)
    raise HTTPException(status_code=500, detail="Internal error")
