"""V2 ORM models.

Mirrors the cumulative state after Alembic revisions:
  * 0002_v2_foundation  — cases, documents, document_versions, processing_events, chunks (placeholder)
  * 0003_v2_retrieval   — chunks fields, embeddings, retrieval_logs

UUID primary keys are stored as String(36) for cross-DB compatibility.
"""
from datetime import datetime
import os
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
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
            "extraction_method IN ('pypdf2', 'textract', 'ocr', 'docx')",
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
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
