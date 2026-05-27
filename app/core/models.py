"""V2 ORM models.

Mirrors the cumulative state after Alembic revisions:
  * 0002_v2_foundation  — cases, documents, document_versions, processing_events, chunks (placeholder)
  * 0003_v2_retrieval   — chunks fields, embeddings, retrieval_logs
  * 0004_min_similarity — retrieval_logs.min_similarity
  * 0005_classification_schema — criteria/section reference, classification, coverage
  * 0006_add_txt_extraction_method — document_versions extraction_method txt
  * 0007_sprint4_schema — citation_text, affinity defaults, generation tables
  * 0010_firm_id_propagation — firms table, cases.firm_id

UUID primary keys are stored as String(36) for cross-DB compatibility.
"""
from datetime import datetime
import os
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))


def _uuid() -> str:
    return str(uuid.uuid4())


class Firm(Base):
    __tablename__ = "firms"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    cases = relationship("Case", back_populates="firm", cascade="save-update, merge")


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            "visa_type IN ('EB1', 'EB2')",
            name="ck_cases_visa_type",
        ),
        CheckConstraint(
            "status IN ('active', 'closed', 'on_hold')",
            name="ck_cases_status",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    firm_id = Column(
        String(36),
        ForeignKey("firms.id", ondelete="RESTRICT", name="fk_cases_firm_id"),
        nullable=False,
        index=True,
    )
    case_ref = Column(String(100), nullable=False, unique=True, index=True)
    visa_type = Column(String(20), nullable=False)
    status = Column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    created_by = Column(String(255), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    firm = relationship("Firm", back_populates="cases")
    documents = relationship(
        "Document",
        back_populates="case",
        cascade="save-update, merge",
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_state IN ("
            "'received', 'ingested', 'chunked', 'embedded', "
            "'indexed', 'reviewed', 'final'"
            ")",
            name="ck_documents_lifecycle_state",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(
        String(36),
        ForeignKey("cases.id", ondelete="RESTRICT", name="fk_documents_case_id"),
        nullable=False,
        index=True,
    )
    original_name = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    s3_raw_key = Column(String(1000), nullable=False)
    lifecycle_state = Column(
        String(30),
        nullable=False,
        default="received",
        server_default="received",
        index=True,
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    case = relationship("Case", back_populates="documents")
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="save-update, merge",
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_id_version_number",
        ),
        CheckConstraint(
            "extraction_method IN ('pypdf2', 'textract', 'ocr', 'docx', 'txt')",
            name="ck_document_versions_extraction_method",
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'completed', 'failed', 'skipped')",
            name="ck_document_versions_extraction_status",
        ),
        # Marker: this table is append-only. No UPDATE statements should be
        # issued against it anywhere in the codebase. Insert a new row with
        # an incremented version_number instead.
        {"info": {"append_only": True}},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(
        String(36),
        ForeignKey(
            "documents.id",
            ondelete="RESTRICT",
            name="fk_document_versions_document_id",
        ),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False, default=1, server_default="1")
    content_hash = Column(String(64), nullable=False, index=True)
    extraction_method = Column(String(50), nullable=True)
    extraction_status = Column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    extracted_text_s3_key = Column(String(1000), nullable=True)
    page_count = Column(Integer, nullable=True)
    extracted_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    document = relationship("Document", back_populates="versions")
    events = relationship(
        "ProcessingEvent",
        back_populates="document_version",
        cascade="save-update, merge",
    )


class ProcessingEvent(Base):
    __tablename__ = "processing_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'skipped')",
            name="ck_processing_events_status",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(
        String(36),
        ForeignKey("cases.id", name="fk_processing_events_case_id"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        String(36),
        ForeignKey("documents.id", name="fk_processing_events_document_id"),
        nullable=True,
        index=True,
    )
    document_version_id = Column(
        String(36),
        ForeignKey(
            "document_versions.id",
            name="fk_processing_events_document_version_id",
        ),
        nullable=True,
    )
    event_type = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    detail = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    document_version = relationship("DocumentVersion", back_populates="events")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_version_id = Column(
        String(36),
        ForeignKey(
            "document_versions.id", name="fk_chunks_document_version_id"
        ),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=True)
    chunk_strategy = Column(
        String(50),
        nullable=False,
        default="fixed_size",
        server_default="fixed_size",
    )
    chunk_strategy_version = Column(
        String(20),
        nullable=False,
        default="1.0",
        server_default="1.0",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        # Marker: this table is append-only. No UPDATE statements should be
        # issued against it anywhere in the codebase. Insert a new row for
        # any embedding revision (e.g. model_version bump).
        {"info": {"append_only": True}},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    chunk_id = Column(
        String(36),
        ForeignKey(
            "chunks.id", ondelete="RESTRICT", name="fk_embeddings_chunk_id"
        ),
        nullable=False,
        index=True,
    )
    model_name = Column(String(100), nullable=False, index=True)
    model_version = Column(String(50), nullable=False)
    dimensions = Column(Integer, nullable=False)
    vector = Column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(
        String(36),
        ForeignKey(
            "cases.id",
            ondelete="RESTRICT",
            name="fk_retrieval_logs_case_id",
        ),
        nullable=False,
        index=True,
    )
    query_text = Column(Text, nullable=False)
    query_embedding_id = Column(
        String(36),
        ForeignKey(
            "embeddings.id",
            ondelete="SET NULL",
            name="fk_retrieval_logs_query_embedding_id",
        ),
        nullable=True,
    )
    top_k = Column(Integer, nullable=False)
    results_count = Column(Integer, nullable=False)
    min_similarity = Column(Float, nullable=False, default=0.0)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class CriteriaReference(Base):
    __tablename__ = "criteria_reference"
    __table_args__ = (
        CheckConstraint(
            "visa_type IN ('EB1', 'EB2', 'BOTH')",
            name="ck_criteria_reference_visa_type",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), nullable=False, unique=True, index=True)
    visa_type = Column(String(20), nullable=False, index=True)
    label = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    display_order = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class SectionAffinityReference(Base):
    __tablename__ = "section_affinity_reference"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), nullable=False, unique=True)
    label = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    display_order = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class ClassificationResult(Base):
    __tablename__ = "classification_results"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_classification_results_confidence_score",
        ),
        CheckConstraint(
            "classifier_type IN ('llm', 'rule_based', 'hybrid')",
            name="ck_classification_results_classifier_type",
        ),
        {"info": {"append_only": True}},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    chunk_id = Column(
        String(36),
        ForeignKey(
            "chunks.id",
            ondelete="RESTRICT",
            name="fk_classification_results_chunk_id",
        ),
        nullable=False,
        index=True,
    )
    document_version_id = Column(
        String(36),
        ForeignKey(
            "document_versions.id",
            ondelete="RESTRICT",
            name="fk_classification_results_document_version_id",
        ),
        nullable=False,
        index=True,
    )
    case_id = Column(
        String(36),
        ForeignKey(
            "cases.id",
            ondelete="RESTRICT",
            name="fk_classification_results_case_id",
        ),
        nullable=False,
        index=True,
    )
    criteria_id = Column(
        String(36),
        ForeignKey(
            "criteria_reference.id",
            ondelete="RESTRICT",
            name="fk_classification_results_criteria_id",
        ),
        nullable=False,
        index=True,
    )
    section_affinity_id = Column(
        String(36),
        ForeignKey(
            "section_affinity_reference.id",
            ondelete="RESTRICT",
            name="fk_classification_results_section_affinity_id",
        ),
        nullable=False,
        index=True,
    )
    confidence_score = Column(Float, nullable=False)
    rationale = Column(Text, nullable=False)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    classifier_type = Column(String(30), nullable=False)
    citation_text = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class ClassificationFeedback(Base):
    __tablename__ = "classification_feedback"
    __table_args__ = (
        CheckConstraint(
            "action IN ('confirmed', 'rejected', 'corrected')",
            name="ck_classification_feedback_action",
        ),
        CheckConstraint(
            "corrected_confidence_score IS NULL OR "
            "(corrected_confidence_score >= 0.0 AND corrected_confidence_score <= 1.0)",
            name="ck_classification_feedback_corrected_confidence_score",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    classification_result_id = Column(
        String(36),
        ForeignKey(
            "classification_results.id",
            ondelete="RESTRICT",
            name="fk_classification_feedback_classification_result_id",
        ),
        nullable=False,
        index=True,
    )
    case_id = Column(
        String(36),
        ForeignKey(
            "cases.id",
            ondelete="RESTRICT",
            name="fk_classification_feedback_case_id",
        ),
        nullable=False,
        index=True,
    )
    reviewer_id = Column(String(255), nullable=False)
    action = Column(String(30), nullable=False)
    corrected_criteria_id = Column(
        String(36),
        ForeignKey(
            "criteria_reference.id",
            name="fk_classification_feedback_corrected_criteria_id",
        ),
        nullable=True,
    )
    corrected_section_affinity_id = Column(
        String(36),
        ForeignKey(
            "section_affinity_reference.id",
            name="fk_classification_feedback_corrected_section_affinity_id",
        ),
        nullable=True,
    )
    corrected_confidence_score = Column(Float, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class CoverageGap(Base):
    __tablename__ = "coverage_gaps"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "criteria_id",
            name="uq_coverage_gaps_case_id_criteria_id",
        ),
        CheckConstraint(
            "gap_status IN ('covered', 'insufficient', 'missing')",
            name="ck_coverage_gaps_gap_status",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(
        String(36),
        ForeignKey(
            "cases.id",
            ondelete="RESTRICT",
            name="fk_coverage_gaps_case_id",
        ),
        nullable=False,
        index=True,
    )
    criteria_id = Column(
        String(36),
        ForeignKey(
            "criteria_reference.id",
            ondelete="RESTRICT",
            name="fk_coverage_gaps_criteria_id",
        ),
        nullable=False,
    )
    gap_status = Column(String(30), nullable=False)
    chunk_count = Column(Integer, nullable=False, default=0, server_default="0")
    evaluated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class CriteriaSectionAffinityDefault(Base):
    __tablename__ = "criteria_section_affinity_defaults"
    __table_args__ = (
        UniqueConstraint(
            "criteria_id",
            "section_affinity_id",
            "visa_type",
            name="uq_criteria_section_affinity_defaults_criteria_section_visa",
        ),
        CheckConstraint(
            "visa_type IN ('EB1', 'EB2', 'BOTH')",
            name="ck_criteria_section_affinity_defaults_visa_type",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    criteria_id = Column(
        String(36),
        ForeignKey(
            "criteria_reference.id",
            ondelete="RESTRICT",
            name="fk_criteria_section_affinity_defaults_criteria_id",
        ),
        nullable=False,
        index=True,
    )
    section_affinity_id = Column(
        String(36),
        ForeignKey(
            "section_affinity_reference.id",
            ondelete="RESTRICT",
            name="fk_criteria_section_affinity_defaults_section_affinity_id",
        ),
        nullable=False,
    )
    visa_type = Column(String(20), nullable=False)
    priority = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint(
            "visa_type",
            "section_code",
            "version",
            name="uq_prompt_templates_visa_type_section_code_version",
        ),
        CheckConstraint(
            "visa_type IN ('EB1', 'EB2', 'BOTH')",
            name="ck_prompt_templates_visa_type",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    visa_type = Column(String(20), nullable=False, index=True)
    section_code = Column(String(50), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    examples = Column(Text, nullable=True)
    model_name = Column(String(100), nullable=False, default="gpt-4o", server_default="gpt-4o")
    max_tokens = Column(Integer, nullable=False, default=1000, server_default="1000")
    temperature = Column(Float, nullable=False, default=0.3, server_default="0.3")
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class DraftOutput(Base):
    __tablename__ = "draft_outputs"
    __table_args__ = (
        CheckConstraint(
            "visa_type IN ('EB1', 'EB2')",
            name="ck_draft_outputs_visa_type",
        ),
        CheckConstraint(
            "overall_status IN ('complete', 'incomplete', 'coverage_override')",
            name="ck_draft_outputs_overall_status",
        ),
        {"info": {"append_only": True}},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(
        String(36),
        ForeignKey(
            "cases.id",
            ondelete="RESTRICT",
            name="fk_draft_outputs_case_id",
        ),
        nullable=False,
        index=True,
    )
    visa_type = Column(String(20), nullable=False)
    document_version_id = Column(
        String(36),
        ForeignKey(
            "document_versions.id",
            ondelete="RESTRICT",
            name="fk_draft_outputs_document_version_id",
        ),
        nullable=False,
    )
    overall_status = Column(String(30), nullable=False)
    coverage_summary = Column(JSONB, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class DraftSection(Base):
    __tablename__ = "draft_sections"
    __table_args__ = ({"info": {"append_only": True}},)

    id = Column(String(36), primary_key=True, default=_uuid)
    draft_output_id = Column(
        String(36),
        ForeignKey(
            "draft_outputs.id",
            ondelete="RESTRICT",
            name="fk_draft_sections_draft_output_id",
        ),
        nullable=False,
        index=True,
    )
    section_code = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    prompt_template_id = Column(
        String(36),
        ForeignKey(
            "prompt_templates.id",
            ondelete="RESTRICT",
            name="fk_draft_sections_prompt_template_id",
        ),
        nullable=False,
    )
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )


class GenerationTrace(Base):
    __tablename__ = "generation_traces"
    __table_args__ = ({"info": {"append_only": True}},)

    id = Column(String(36), primary_key=True, default=_uuid)
    draft_section_id = Column(
        String(36),
        ForeignKey(
            "draft_sections.id",
            ondelete="RESTRICT",
            name="fk_generation_traces_draft_section_id",
        ),
        nullable=False,
        index=True,
    )
    chunk_id = Column(
        String(36),
        ForeignKey(
            "chunks.id",
            ondelete="RESTRICT",
            name="fk_generation_traces_chunk_id",
        ),
        nullable=False,
        index=True,
    )
    classification_result_id = Column(
        String(36),
        ForeignKey(
            "classification_results.id",
            ondelete="RESTRICT",
            name="fk_generation_traces_classification_result_id",
        ),
        nullable=False,
        index=True,
    )
    citation_text = Column(Text, nullable=True)
    similarity_score = Column(Float, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
