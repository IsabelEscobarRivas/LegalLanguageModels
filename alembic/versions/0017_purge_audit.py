"""Admin purge audit log schema.

Revision ID: 0017_purge_audit
Revises: 0016_participation_audit
Create Date: 2026-05-27

Adds append-only admin_purge_log for restricted physical purge actions
in Sprint 7.5D. Extends lifecycle CHECK constraints to allow purged state.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0017_purge_audit"
down_revision = "0016_participation_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_purge_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("firm_id", sa.String(36), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "target_type IN ('document','kb_document','draft_output')",
            name="ck_purge_log_target_type",
        ),
        sa.CheckConstraint(
            "action IN ('hard_delete','s3_purge','db_purge')",
            name="ck_purge_log_action",
        ),
    )
    op.create_index(
        "ix_purge_log_actor_id",
        "admin_purge_log",
        ["actor_id"],
    )
    op.create_index(
        "ix_purge_log_firm_id",
        "admin_purge_log",
        ["firm_id"],
    )
    op.create_index(
        "ix_purge_log_target_id",
        "admin_purge_log",
        ["target_id"],
    )

    op.drop_constraint("ck_documents_lifecycle_state", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_lifecycle_state",
        "documents",
        "lifecycle_state IN ("
        "'received', 'ingested', 'chunked', 'embedded', "
        "'indexed', 'reviewed', 'final', 'ingestion_failed', 'purged'"
        ")",
    )

    op.drop_constraint(
        "ck_kb_documents_lifecycle_state",
        "kb_documents",
        type_="check",
    )
    op.create_check_constraint(
        "ck_kb_documents_lifecycle_state",
        "kb_documents",
        "lifecycle_state IN ("
        "'uploaded', 'chunked', 'embedded', 'indexed', 'purged'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_kb_documents_lifecycle_state",
        "kb_documents",
        type_="check",
    )
    op.create_check_constraint(
        "ck_kb_documents_lifecycle_state",
        "kb_documents",
        "lifecycle_state IN ('uploaded', 'chunked', 'embedded', 'indexed')",
    )

    op.drop_constraint("ck_documents_lifecycle_state", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_lifecycle_state",
        "documents",
        "lifecycle_state IN ("
        "'received', 'ingested', 'chunked', 'embedded', "
        "'indexed', 'reviewed', 'final', 'ingestion_failed'"
        ")",
    )

    op.drop_index("ix_purge_log_target_id", table_name="admin_purge_log")
    op.drop_index("ix_purge_log_firm_id", table_name="admin_purge_log")
    op.drop_index("ix_purge_log_actor_id", table_name="admin_purge_log")
    op.drop_table("admin_purge_log")
