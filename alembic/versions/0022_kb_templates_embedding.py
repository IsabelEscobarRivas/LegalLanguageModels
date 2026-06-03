"""Add embedding column to kb_templates for RAG 2 vector retrieval.

Revision ID: 0022_kb_templates_embedding
Revises: 0021_kb_templates
Create Date: 2026-06-02

Adds pgvector embedding on kb_templates (nullable until backfill/extraction).
Index pattern matches kb_embeddings (0011_kb_schema).
"""
import os

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import text


revision = "0022_kb_templates_embedding"
down_revision = "0021_kb_templates"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))


def upgrade() -> None:
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.add_column(
        "kb_templates",
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True),
    )
    op.execute(
        text(
            "CREATE INDEX ix_kb_templates_vector ON kb_templates "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_kb_templates_vector"))
    op.drop_column("kb_templates", "embedding")
