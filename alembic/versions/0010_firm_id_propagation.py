"""Add firms table and firm_id tenant root on cases.

Revision ID: 0010_firm_id_propagation
Revises: 0009_prompt_templates_seed
Create Date: 2026-05-27

Establishes firm_id as the root tenant identifier per ADR-009. Creates the
firms table, seeds a default firm, and backfills all existing cases.
"""
from alembic import op
from sqlalchemy import text

revision = "0010_firm_id_propagation"
down_revision = "0009_prompt_templates_seed"
branch_labels = None
depends_on = None

DEFAULT_FIRM_ID = "8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b"


def _users_table_exists(conn) -> bool:
    result = conn.execute(
        text(
            "SELECT EXISTS ("
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'users'"
            ")"
        )
    ).scalar()
    return bool(result)


def upgrade() -> None:
    conn = op.get_bind()

    # Step A — Create firms table
    conn.execute(
        text(
            """
            CREATE TABLE firms (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                slug VARCHAR(100) NOT NULL UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP NOT NULL DEFAULT now()
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX ix_firms_slug ON firms (slug)"))

    # Step B — Seed the default firm
    conn.execute(
        text(
            "INSERT INTO firms (id, name, slug) "
            "VALUES (:firm_id, 'Default Firm', 'default')"
        ),
        {"firm_id": DEFAULT_FIRM_ID},
    )

    # Step C — Add firm_id to cases
    conn.execute(
        text(
            "ALTER TABLE cases ADD COLUMN firm_id VARCHAR(36) "
            "REFERENCES firms(id) ON DELETE RESTRICT"
        )
    )
    conn.execute(
        text("UPDATE cases SET firm_id = :firm_id"),
        {"firm_id": DEFAULT_FIRM_ID},
    )
    conn.execute(text("ALTER TABLE cases ALTER COLUMN firm_id SET NOT NULL"))
    conn.execute(text("CREATE INDEX ix_cases_firm_id ON cases (firm_id)"))

    # Step D — Add firm_id to users if table exists
    if _users_table_exists(conn):
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN firm_id VARCHAR(36) "
                "REFERENCES firms(id) ON DELETE RESTRICT"
            )
        )
        conn.execute(
            text("UPDATE users SET firm_id = :firm_id"),
            {"firm_id": DEFAULT_FIRM_ID},
        )
        conn.execute(text("ALTER TABLE users ALTER COLUMN firm_id SET NOT NULL"))
        conn.execute(text("CREATE INDEX ix_users_firm_id ON users (firm_id)"))


def downgrade() -> None:
    conn = op.get_bind()

    if _users_table_exists(conn):
        conn.execute(text("DROP INDEX IF EXISTS ix_users_firm_id"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS firm_id"))

    conn.execute(text("DROP INDEX IF EXISTS ix_cases_firm_id"))
    conn.execute(text("ALTER TABLE cases DROP COLUMN firm_id"))
    conn.execute(text("DROP TABLE firms"))
