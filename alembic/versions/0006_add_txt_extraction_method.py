"""add txt to document_versions extraction_method check constraint

Revision ID: 0006_add_txt_extraction_method
Revises: 0005_classification_schema
Create Date: 2026-05-26

Allows extraction_method='txt' for plain-text uploads decoded via UTF-8.
"""
from alembic import op


revision = "0006_add_txt_extraction_method"
down_revision = "0005_classification_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_versions
          DROP CONSTRAINT IF EXISTS ck_document_versions_extraction_method
        """
    )
    op.execute(
        """
        ALTER TABLE document_versions
          ADD CONSTRAINT ck_document_versions_extraction_method
          CHECK (extraction_method IN ('pypdf2','textract','ocr','docx','txt'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_versions
          DROP CONSTRAINT IF EXISTS ck_document_versions_extraction_method
        """
    )
    op.execute(
        """
        ALTER TABLE document_versions
          ADD CONSTRAINT ck_document_versions_extraction_method
          CHECK (extraction_method IN ('pypdf2','textract','ocr','docx'))
        """
    )
