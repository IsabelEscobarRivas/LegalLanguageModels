"""Add kb_templates table for structured KB style templates per section.

Revision ID: 0021_kb_templates
Revises: 0020_petition_prompt_templates
Create Date: 2026-06-02

Stores extracted template structure linked to kb_chunks for generation-time
retrieval by firm_id and section_key. SQLAlchemy model deferred to a follow-up.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0021_kb_templates"
down_revision = "0020_petition_prompt_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "kb_chunk_id",
            sa.String(36),
            sa.ForeignKey(
                "kb_chunks.id",
                ondelete="RESTRICT",
                name="fk_kb_templates_kb_chunk_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_kb_templates_firm_id",
            ),
            nullable=False,
        ),
        sa.Column("visa_type", sa.String(50), nullable=False),
        sa.Column("section_key", sa.String(100), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("evidence_placeholders", JSONB(), nullable=True),
        sa.Column("argument_sequence", JSONB(), nullable=True),
        sa.Column("tone_guidance", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "extraction_prompt_version",
            sa.String(20),
            nullable=False,
            server_default="1.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_kb_templates_firm_id_section_key",
        "kb_templates",
        ["firm_id", "section_key"],
    )
    op.create_index(
        "ix_kb_templates_kb_chunk_id",
        "kb_templates",
        ["kb_chunk_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_kb_templates_kb_chunk_id", table_name="kb_templates")
    op.drop_index(
        "ix_kb_templates_firm_id_section_key",
        table_name="kb_templates",
    )
    op.drop_table("kb_templates")
