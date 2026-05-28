"""Reviewer notes on draft section reviews.

Revision ID: 0018_reviewer_notes
Revises: 0017_purge_audit
Create Date: 2026-05-28

Adds optional reviewer_notes to draft_section_reviews for Sprint 7.5E.
"""
from alembic import op
import sqlalchemy as sa


revision = "0018_reviewer_notes"
down_revision = "0017_purge_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "draft_section_reviews",
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("draft_section_reviews", "reviewer_notes")
