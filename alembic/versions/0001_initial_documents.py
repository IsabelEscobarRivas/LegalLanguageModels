"""initial documents table

Revision ID: 0001_initial_documents
Revises:
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial_documents"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("s3_url", sa.String(), nullable=True),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("visa_type", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("document_metadata", sa.JSON(), nullable=True),
        sa.Column("document_type", sa.String(), nullable=True),
        sa.Column("relevant_sections", sa.JSON(), nullable=True),
    )
    op.create_index("ix_documents_filename", "documents", ["filename"])
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_visa_type", "documents", ["visa_type"])
    op.create_index("ix_documents_category", "documents", ["category"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])


def downgrade() -> None:
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_category", table_name="documents")
    op.drop_index("ix_documents_visa_type", table_name="documents")
    op.drop_index("ix_documents_case_id", table_name="documents")
    op.drop_index("ix_documents_filename", table_name="documents")
    op.drop_table("documents")
