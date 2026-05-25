"""add min_similarity column to retrieval_logs

Revision ID: 0004_add_min_similarity_to_retrieval_logs
Revises: 0003_v2_retrieval
Create Date: 2026-05-25

Adds the `min_similarity` threshold column to `retrieval_logs` so every
retrieval log row records the cosine-similarity threshold applied at
query time. NOT NULL with a server-side default of 0.0 so existing rows
back-fill cleanly (0.0 = "no threshold applied", which matches the
behavior of all pre-S3-D01 retrieval calls).
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_min_similarity"
down_revision = "0003_v2_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_logs",
        sa.Column(
            "min_similarity",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )


def downgrade() -> None:
    op.drop_column("retrieval_logs", "min_similarity")
