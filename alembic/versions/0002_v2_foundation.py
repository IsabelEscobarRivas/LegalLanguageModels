"""v2 foundation: cases, documents, document_versions, processing_events, chunks

Revision ID: 0002_v2_foundation
Revises: 0001_initial_documents
Create Date: 2026-05-23

Replaces the V1 monolithic `documents` table with the normalized V2 schema.
V1 data is intentionally discarded (spec: V1 data loss is acceptable).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_v2_foundation"
down_revision = "0001_initial_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the V1 monolithic documents table and its indexes first.
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_category", table_name="documents")
    op.drop_index("ix_documents_visa_type", table_name="documents")
    op.drop_index("ix_documents_case_id", table_name="documents")
    op.drop_index("ix_documents_filename", table_name="documents")
    op.drop_table("documents")

    # cases
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_ref", sa.String(100), nullable=False),
        sa.Column("visa_type", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("case_ref", name="uq_cases_case_ref"),
        sa.CheckConstraint(
            "visa_type IN ('EB1', 'EB2')",
            name="ck_cases_visa_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'closed', 'on_hold')",
            name="ck_cases_status",
        ),
    )
    op.create_index("ix_cases_case_ref", "cases", ["case_ref"])
    op.create_index("ix_cases_status", "cases", ["status"])

    # documents
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="RESTRICT", name="fk_documents_case_id"),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("s3_raw_key", sa.String(1000), nullable=False),
        sa.Column(
            "lifecycle_state",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ("
            "'received', 'ingested', 'chunked', 'embedded', "
            "'indexed', 'reviewed', 'final'"
            ")",
            name="ck_documents_lifecycle_state",
        ),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_lifecycle_state", "documents", ["lifecycle_state"])

    # document_versions (append-only)
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey(
                "documents.id",
                ondelete="RESTRICT",
                name="fk_document_versions_document_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extraction_method", sa.String(50), nullable=True),
        sa.Column(
            "extraction_status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("extracted_text_s3_key", sa.String(1000), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_id_version_number",
        ),
        sa.CheckConstraint(
            "extraction_method IN ('pypdf2', 'textract', 'ocr', 'docx')",
            name="ck_document_versions_extraction_method",
        ),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'completed', 'failed', 'skipped')",
            name="ck_document_versions_extraction_status",
        ),
    )
    op.create_index(
        "ix_document_versions_document_id", "document_versions", ["document_id"]
    )
    op.create_index(
        "ix_document_versions_content_hash", "document_versions", ["content_hash"]
    )

    # processing_events
    op.create_table(
        "processing_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", name="fk_processing_events_case_id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", name="fk_processing_events_document_id"),
            nullable=True,
        ),
        sa.Column(
            "document_version_id",
            sa.String(36),
            sa.ForeignKey(
                "document_versions.id",
                name="fk_processing_events_document_version_id",
            ),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'skipped')",
            name="ck_processing_events_status",
        ),
    )
    op.create_index("ix_processing_events_case_id", "processing_events", ["case_id"])
    op.create_index(
        "ix_processing_events_document_id", "processing_events", ["document_id"]
    )
    op.create_index(
        "ix_processing_events_event_type", "processing_events", ["event_type"]
    )

    # chunks (placeholder only — no logic, no extra columns)
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_version_id",
            sa.String(36),
            sa.ForeignKey(
                "document_versions.id", name="fk_chunks_document_version_id"
            ),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    # Drop V2 tables in reverse dependency order.
    op.drop_table("chunks")

    op.drop_index("ix_processing_events_event_type", table_name="processing_events")
    op.drop_index("ix_processing_events_document_id", table_name="processing_events")
    op.drop_index("ix_processing_events_case_id", table_name="processing_events")
    op.drop_table("processing_events")

    op.drop_index(
        "ix_document_versions_content_hash", table_name="document_versions"
    )
    op.drop_index(
        "ix_document_versions_document_id", table_name="document_versions"
    )
    op.drop_table("document_versions")

    op.drop_index("ix_documents_lifecycle_state", table_name="documents")
    op.drop_index("ix_documents_case_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_case_ref", table_name="cases")
    op.drop_table("cases")

    # Recreate V1 `documents` as a minimal stub so 0001's downgrade
    # (which drops `documents`) remains valid.
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
    )
