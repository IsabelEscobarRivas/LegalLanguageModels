"""Review and export schema for Sprint 7A.

Revision ID: 0014_review_export_schema
Revises: 0013_kb_guidance_prompt_inst
Create Date: 2026-05-27

Adds append-only draft_section_reviews and draft_exports tables for the
human review workflow defined in ADR-011.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0014_review_export_schema"
down_revision = "0013_kb_guidance_prompt_inst"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "draft_section_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "draft_section_id",
            sa.String(36),
            sa.ForeignKey(
                "draft_sections.id",
                ondelete="RESTRICT",
                name="fk_draft_section_reviews_draft_section_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_draft_section_reviews_case_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_draft_section_reviews_firm_id",
            ),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("reviewer_edit", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "regeneration_requested",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "regenerated_section_id",
            sa.String(36),
            sa.ForeignKey(
                "draft_sections.id",
                name="fk_draft_section_reviews_regenerated_section_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('approved', 'rejected', 'edited')",
            name="ck_draft_section_reviews_action",
        ),
    )
    op.create_index(
        "ix_draft_section_reviews_draft_section_id",
        "draft_section_reviews",
        ["draft_section_id"],
    )
    op.create_index(
        "ix_draft_section_reviews_case_id",
        "draft_section_reviews",
        ["case_id"],
    )
    op.create_index(
        "ix_draft_section_reviews_firm_id",
        "draft_section_reviews",
        ["firm_id"],
    )

    op.create_table(
        "draft_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "draft_output_id",
            sa.String(36),
            sa.ForeignKey(
                "draft_outputs.id",
                ondelete="RESTRICT",
                name="fk_draft_exports_draft_output_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_draft_exports_case_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_draft_exports_firm_id",
            ),
            nullable=False,
        ),
        sa.Column("exported_by", sa.String(255), nullable=False),
        sa.Column("export_format", sa.String(30), nullable=False),
        sa.Column("section_snapshot", JSONB(), nullable=False),
        sa.Column("review_snapshot", JSONB(), nullable=False),
        sa.Column("s3_export_key", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "export_format IN ('json', 'txt', 'pdf')",
            name="ck_draft_exports_export_format",
        ),
    )
    op.create_index(
        "ix_draft_exports_draft_output_id",
        "draft_exports",
        ["draft_output_id"],
    )
    op.create_index(
        "ix_draft_exports_case_id",
        "draft_exports",
        ["case_id"],
    )
    op.create_index(
        "ix_draft_exports_firm_id",
        "draft_exports",
        ["firm_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_draft_exports_firm_id", table_name="draft_exports")
    op.drop_index("ix_draft_exports_case_id", table_name="draft_exports")
    op.drop_index("ix_draft_exports_draft_output_id", table_name="draft_exports")
    op.drop_table("draft_exports")

    op.drop_index("ix_draft_section_reviews_firm_id", table_name="draft_section_reviews")
    op.drop_index("ix_draft_section_reviews_case_id", table_name="draft_section_reviews")
    op.drop_index(
        "ix_draft_section_reviews_draft_section_id",
        table_name="draft_section_reviews",
    )
    op.drop_table("draft_section_reviews")
