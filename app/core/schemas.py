"""Pydantic request and response models for the V2 API.

All response models use `model_config = ConfigDict(from_attributes=True)` so
they can be constructed directly from ORM instances.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Cases ----------

class CaseCreate(BaseModel):
    case_ref: str = Field(..., min_length=1, max_length=100)
    visa_type: Literal["EB1", "EB2"]


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_ref: str
    visa_type: str
    status: str
    created_at: datetime


# ---------- Documents (list / detail / upload) ----------

class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    lifecycle_state: str
    version_count: int
    created_at: datetime


class CaseDocumentList(BaseModel):
    case_id: str
    documents: list[DocumentSummary]


class LatestVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    extraction_status: str
    extracted_at: Optional[datetime] = None


class DocumentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    original_name: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    lifecycle_state: str
    s3_raw_key: str
    created_at: datetime
    latest_version: Optional[LatestVersion] = None


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    version_id: str
    version_number: int
    case_id: str
    original_name: str
    lifecycle_state: str
    extraction_status: str
    s3_raw_key: str
    created_at: datetime


# ---------- DocumentVersions ----------

class DocumentVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    content_hash: str
    extraction_method: Optional[str] = None
    extraction_status: str
    page_count: Optional[int] = None
    extracted_at: Optional[datetime] = None
    created_at: datetime


class DocumentVersionList(BaseModel):
    document_id: str
    versions: list[DocumentVersionSummary]


# ---------- Processing events ----------

class ProcessingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    status: str
    detail: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime


class VersionEventList(BaseModel):
    version_id: str
    events: list[ProcessingEventResponse]


# ---------- Case events (Sprint 2) ----------

class ProcessingEventDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    status: str
    document_id: Optional[str] = None
    document_version_id: Optional[str] = None
    detail: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime


class CaseEventList(BaseModel):
    case_id: str
    events: list[ProcessingEventDetail]


# ---------- Retrieval (Sprint 2 / S3-D01) ----------

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.0, ge=0.0, le=1.0)


# ---------- Classification feedback and coverage (Sprint 3) ----------

class ClassificationFeedbackRequest(BaseModel):
    action: Literal["confirmed", "rejected", "corrected"]
    corrected_criteria_id: Optional[str] = None
    corrected_section_affinity_id: Optional[str] = None
    corrected_confidence_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    rationale: Optional[str] = None


class ClassificationFeedbackResponse(BaseModel):
    id: str
    classification_result_id: str
    action: str
    created_at: datetime


class CoverageCriterionResult(BaseModel):
    criteria_id: str
    criteria_code: str
    criteria_label: str
    gap_status: str
    chunk_count: int


class CoverageResponse(BaseModel):
    case_id: str
    visa_type: str
    overall_status: str
    evaluated_at: str
    coverage: list[CoverageCriterionResult]
