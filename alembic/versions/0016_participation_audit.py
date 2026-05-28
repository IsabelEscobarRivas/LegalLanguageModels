"""Document participation governance audit trail.

Revision ID: 0016_participation_audit
Revises: 0015_extraction_confidence
Create Date: 2026-05-27

Adds append-only document_participation_events for governance actions
(exclusion, quarantine, archive, restore) in Sprint 7.5B.
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_participation_audit"
down_revision = "0015_extraction_confidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_participation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey(
                "documents.id",
                ondelete="RESTRICT",
                name="fk_dpe_document_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey(
                "cases.id",
                ondelete="RESTRICT",
                name="fk_dpe_case_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "firm_id",
            sa.String(36),
            sa.ForeignKey(
                "firms.id",
                ondelete="RESTRICT",
                name="fk_dpe_firm_id",
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("previous_state", sa.String(50), nullable=False),
        sa.Column("new_state", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ("
            "'excluded_from_retrieval', 'excluded_from_generation', "
            "'archived', 'quarantined', 'superseded', 'restored', "
            "'marked_ingestion_failed'"
            ")",
            name="ck_dpe_action",
        ),
    )
    op.create_index(
        "ix_dpe_document_id",
        "document_participation_events",
        ["document_id"],
    )
    op.create_index(
        "ix_dpe_case_id",
        "document_participation_events",
        ["case_id"],
    )
    op.create_index(
        "ix_dpe_firm_id",
        "document_participation_events",
        ["firm_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dpe_firm_id", table_name="document_participation_events")
    op.drop_index("ix_dpe_case_id", table_name="document_participation_events")
    op.drop_index("ix_dpe_document_id", table_name="document_participation_events")
    op.drop_table("document_participation_events")
