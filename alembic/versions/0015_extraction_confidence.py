"""Extraction confidence and integrity validation schema.

Revision ID: 0015_extraction_confidence
Revises: 0014_review_export_schema
Create Date: 2026-05-27

Adds extraction quality metrics on document_versions and participation
eligibility flags on documents for Sprint 7.5A integrity gating.
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_extraction_confidence"
down_revision = "0014_review_export_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_versions",
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("text_density", sa.Float(), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "integrity_status",
            sa.String(50),
            nullable=True,
            server_default=sa.text("'pending'"),
        ),
    )
    op.create_check_constraint(
        "ck_document_versions_integrity_status",
        "document_versions",
        "integrity_status IN ("
        "'pending', 'passed', 'failed_low_confidence', 'failed_low_density', "
        "'failed_corruption', 'passed_ocr'"
        ")",
    )

    op.add_column(
        "documents",
        sa.Column(
            "retrieval_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "generation_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "participation_state",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.create_check_constraint(
        "ck_documents_participation_state",
        "documents",
        "participation_state IN ("
        "'active', 'excluded_from_retrieval', 'excluded_from_generation', "
        "'archived', 'superseded', 'quarantined', 'ingestion_failed'"
        ")",
    )

    op.drop_constraint("ck_documents_lifecycle_state", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_lifecycle_state",
        "documents",
        "lifecycle_state IN ("
        "'received', 'ingested', 'chunked', 'embedded', "
        "'indexed', 'reviewed', 'final', 'ingestion_failed'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_lifecycle_state", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_lifecycle_state",
        "documents",
        "lifecycle_state IN ("
        "'received', 'ingested', 'chunked', 'embedded', "
        "'indexed', 'reviewed', 'final'"
        ")",
    )

    op.drop_constraint("ck_documents_participation_state", "documents", type_="check")
    op.drop_column("documents", "participation_state")
    op.drop_column("documents", "generation_eligible")
    op.drop_column("documents", "retrieval_eligible")

    op.drop_constraint(
        "ck_document_versions_integrity_status",
        "document_versions",
        type_="check",
    )
    op.drop_column("document_versions", "integrity_status")
    op.drop_column("document_versions", "text_density")
    op.drop_column("document_versions", "extraction_confidence")
