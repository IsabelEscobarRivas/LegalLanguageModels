"""Classification endpoints.

POST /cases/{case_id}/chunks/{chunk_id}/classify
POST /cases/{case_id}/classify-version
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.classification.classifier import (
    classify_chunk,
    classify_document_version,
)
from app.core.auth import require_case_access
from app.core.database import get_db


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
    """Classify all chunks for a document version."""
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
