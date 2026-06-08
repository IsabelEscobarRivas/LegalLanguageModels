"""Deduplicate kb_templates and add content_hash + unique constraint.

Revision ID: 0024_kb_templates_dedup
Revises: 0023_kb_examples_prompt_inj
Create Date: 2026-06-07

Per ADR-015: remove duplicate (kb_chunk_id, section_key) rows, add
content_hash for future cross-document dedup, enforce uniqueness at DB level.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "0024_kb_templates_dedup"
down_revision = "0023_kb_examples_prompt_inj"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            DELETE FROM kb_templates
            WHERE id NOT IN (
                SELECT DISTINCT ON (kb_chunk_id, section_key) id
                FROM kb_templates
                ORDER BY kb_chunk_id, section_key, created_at ASC
            )
            """
        )
    )
    op.add_column(
        "kb_templates",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_kb_templates_chunk_section",
        "kb_templates",
        ["kb_chunk_id", "section_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_kb_templates_chunk_section",
        "kb_templates",
        type_="unique",
    )
    op.drop_column("kb_templates", "content_hash")
