"""Add applicant_name to cases.

Revision ID: 0025_cases_applicant_name
Revises: 0024_kb_templates_dedup
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa


revision = "0025_cases_applicant_name"
down_revision = "0024_kb_templates_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("applicant_name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "applicant_name")
