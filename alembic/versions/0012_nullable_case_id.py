"""Make processing_events.case_id nullable for KB pipeline events.

Revision ID: 0012_nullable_case_id
Revises: 0011_kb_schema
Create Date: 2026-05-27

KB pipeline events are not case-scoped. Nullable case_id unblocks event writes
from app/kb/pipeline.py with case_id=None.
"""
from alembic import op
from sqlalchemy import text

revision = "0012_nullable_case_id"
down_revision = "0011_kb_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("ALTER TABLE processing_events ALTER COLUMN case_id DROP NOT NULL"))


def downgrade() -> None:
    # Backfill any null case_id rows before re-adding NOT NULL
    # Use a sentinel case_id that will not conflict with real data
    op.execute(text(
        "UPDATE processing_events SET case_id = '00000000-0000-0000-0000-000000000000' "
        "WHERE case_id IS NULL"
    ))
    op.execute(text("ALTER TABLE processing_events ALTER COLUMN case_id SET NOT NULL"))
