"""v2 retrieval foundation: chunk fields, embeddings table, retrieval_logs table

Revision ID: 0003_v2_retrieval
Revises: 0002_v2_foundation
Create Date: 2026-05-24

Adds the columns required to make `chunks` a real chunk record, introduces the
append-only `embeddings` table backed by pgvector, and introduces
`retrieval_logs` for query auditing. pgvector's CREATE EXTENSION runs first;
the embedding vector dimension is read from the EMBEDDING_DIMENSIONS env var
(default 1536) at migration time.
"""
import os

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0003_v2_retrieval"
down_revision = "0002_v2_foundation"
branch_labels = None
depends_on = None


EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))


def upgrade() -> None:
    # pgvector extension must exist before any `vector` columns can be created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---- chunks: promote from placeholder to real chunk record ----
    op.add_column("chunks", sa.Column("text", sa.Text(), nullable=False))
    op.add_column("chunks", sa.Column("char_start", sa.Integer(), nullable=False))
    op.add_column("chunks", sa.Column("char_end", sa.Integer(), nullable=False))
    op.add_column("chunks", sa.Column("token_count", sa.Integer(), nullable=True))
    op.add_column(
        "chunks",
        sa.Column(
            "chunk_strategy",
            sa.String(50),
            nullable=False,
            server_default="fixed_size",
        ),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "chunk_strategy_version",
            sa.String(20),
            nullable=False,
            server_default="1.0",
        ),
    )

    # ---- embeddings (append-only) ----
    op.create_table(
        "embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.String(36),
            sa.ForeignKey(
                "chunks.id", ondelete="RESTRICT", name="fk_embeddings_chunk_id"
            ),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_embeddings_chunk_id", "embeddings", ["chunk_id"])
    op.create_index("ix_embeddings_model_name", "embeddings", ["model_name"])

    # ---- retrieval_logs ----
    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_retrieval_logs_case_id",
            ),
            nullable=False,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column(
            "query_embedding_id",
            sa.String(36),
            sa.ForeignKey(
                "embeddings.id",
                ondelete="SET NULL",
                name="fk_retrieval_logs_query_embedding_id",
            ),
            nullable=True,
        ),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_retrieval_logs_case_id", "retrieval_logs", ["case_id"]
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_index("ix_retrieval_logs_case_id", table_name="retrieval_logs")
    op.drop_table("retrieval_logs")

    op.drop_index("ix_embeddings_model_name", table_name="embeddings")
    op.drop_index("ix_embeddings_chunk_id", table_name="embeddings")
    op.drop_table("embeddings")

    op.drop_column("chunks", "chunk_strategy_version")
    op.drop_column("chunks", "chunk_strategy")
    op.drop_column("chunks", "token_count")
    op.drop_column("chunks", "char_end")
    op.drop_column("chunks", "char_start")
    op.drop_column("chunks", "text")

    op.execute("DROP EXTENSION IF EXISTS vector")
