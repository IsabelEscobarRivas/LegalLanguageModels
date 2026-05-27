"""KB persistence layer: kb_documents, kb_chunks, kb_embeddings, kb_guidance_traces.

Revision ID: 0011_kb_schema
Revises: 0010_firm_id_propagation
Create Date: 2026-05-27

Establishes firm-scoped KB tables and kb_guidance_traces, separate from
generation_traces. Adds draft_sections.kb_guidance_applied for audit visibility.
"""
import os

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import text

revision = "0011_kb_schema"
down_revision = "0010_firm_id_propagation"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))


def upgrade() -> None:
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "kb_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_kb_documents_firm_id",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(1000), nullable=False),
        sa.Column(
            "lifecycle_state",
            sa.String(50),
            nullable=False,
            server_default="uploaded",
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
            "document_type IN ('style_guide', 'firm_convention', 'precedent_letter')",
            name="ck_kb_documents_document_type",
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('uploaded', 'chunked', 'embedded', 'indexed')",
            name="ck_kb_documents_lifecycle_state",
        ),
    )
    op.create_index("ix_kb_documents_firm_id", "kb_documents", ["firm_id"])
    op.create_index(
        "ix_kb_documents_document_type", "kb_documents", ["document_type"]
    )

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_kb_chunks_firm_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "kb_document_id",
            sa.String(36),
            sa.ForeignKey(
                "kb_documents.id",
                ondelete="RESTRICT",
                name="fk_kb_chunks_kb_document_id",
            ),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("chunk_strategy", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_kb_chunks_firm_id", "kb_chunks", ["firm_id"])
    op.create_index(
        "ix_kb_chunks_kb_document_id", "kb_chunks", ["kb_document_id"]
    )

    op.create_table(
        "kb_embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_kb_embeddings_firm_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "kb_chunk_id",
            sa.String(36),
            sa.ForeignKey(
                "kb_chunks.id",
                ondelete="RESTRICT",
                name="fk_kb_embeddings_kb_chunk_id",
            ),
            nullable=False,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_kb_embeddings_firm_id", "kb_embeddings", ["firm_id"])
    op.create_index(
        "ix_kb_embeddings_kb_chunk_id", "kb_embeddings", ["kb_chunk_id"]
    )
    op.execute(
        text(
            "CREATE INDEX ix_kb_embeddings_vector ON kb_embeddings "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )
    )

    op.create_table(
        "kb_guidance_traces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "draft_section_id",
            sa.String(36),
            sa.ForeignKey(
                "draft_sections.id",
                ondelete="RESTRICT",
                name="fk_kb_guidance_traces_draft_section_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "kb_chunk_id",
            sa.String(36),
            sa.ForeignKey(
                "kb_chunks.id",
                ondelete="RESTRICT",
                name="fk_kb_guidance_traces_kb_chunk_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_kb_guidance_traces_firm_id",
            ),
            nullable=False,
        ),
        sa.Column("guidance_type", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "guidance_type IN ('style', 'rhetorical', 'convention')",
            name="ck_kb_guidance_traces_guidance_type",
        ),
    )
    op.create_index(
        "ix_kb_guidance_traces_draft_section_id",
        "kb_guidance_traces",
        ["draft_section_id"],
    )
    op.create_index(
        "ix_kb_guidance_traces_firm_id", "kb_guidance_traces", ["firm_id"]
    )

    op.execute(
        text(
            "ALTER TABLE draft_sections "
            "ADD COLUMN kb_guidance_applied BOOLEAN NOT NULL DEFAULT false"
        )
    )


def downgrade() -> None:
    op.execute(
        text("ALTER TABLE draft_sections DROP COLUMN kb_guidance_applied")
    )

    op.drop_index(
        "ix_kb_guidance_traces_firm_id", table_name="kb_guidance_traces"
    )
    op.drop_index(
        "ix_kb_guidance_traces_draft_section_id",
        table_name="kb_guidance_traces",
    )
    op.drop_table("kb_guidance_traces")

    op.execute(text("DROP INDEX IF EXISTS ix_kb_embeddings_vector"))
    op.drop_index("ix_kb_embeddings_kb_chunk_id", table_name="kb_embeddings")
    op.drop_index("ix_kb_embeddings_firm_id", table_name="kb_embeddings")
    op.drop_table("kb_embeddings")

    op.drop_index("ix_kb_chunks_kb_document_id", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_firm_id", table_name="kb_chunks")
    op.drop_table("kb_chunks")

    op.drop_index("ix_kb_documents_document_type", table_name="kb_documents")
    op.drop_index("ix_kb_documents_firm_id", table_name="kb_documents")
    op.drop_table("kb_documents")
