"""Sprint 4 closure: add background as priority-3 affinity for EB2_NIW_C2

Revision ID: 0008_background_affinity_fix
Revises: 0007_sprint4_schema
Create Date: 2026-05-26

The background section was receiving zero evidence because EB2_NIW_C2
(advanced degree / exceptional ability) had no background routing entry.
CV education content satisfies EB2_NIW_C2 and should route to background
at priority 3, after experience (1) and achievements (2).
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0008_background_affinity_fix"
down_revision = "0007_sprint4_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    section_rows = conn.execute(
        text("SELECT id, code FROM section_affinity_reference")
    ).fetchall()
    section_map = {row[1]: row[0] for row in section_rows}

    criteria_rows = conn.execute(
        text("SELECT id, code FROM criteria_reference")
    ).fetchall()
    criteria_map = {row[1]: row[0] for row in criteria_rows}

    criteria_id = criteria_map.get("EB2_NIW_C2")
    section_id = section_map.get("background")

    if not criteria_id or not section_id:
        raise RuntimeError(
            "EB2_NIW_C2 or background not found in reference tables. "
            "Cannot apply background affinity fix."
        )

    existing = conn.execute(
        text(
            "SELECT id FROM criteria_section_affinity_defaults "
            "WHERE criteria_id = :cid AND section_affinity_id = :sid AND visa_type = 'EB2'"
        ),
        {"cid": criteria_id, "sid": section_id},
    ).fetchone()

    if existing:
        return

    affinity_table = sa.table(
        "criteria_section_affinity_defaults",
        sa.column("id"),
        sa.column("criteria_id"),
        sa.column("section_affinity_id"),
        sa.column("visa_type"),
        sa.column("priority"),
    )

    op.bulk_insert(
        affinity_table,
        [
            {
                "id": str(uuid.uuid4()),
                "criteria_id": criteria_id,
                "section_affinity_id": section_id,
                "visa_type": "EB2",
                "priority": 3,
            }
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()

    section_rows = conn.execute(
        text("SELECT id, code FROM section_affinity_reference")
    ).fetchall()
    section_map = {row[1]: row[0] for row in section_rows}

    criteria_rows = conn.execute(
        text("SELECT id, code FROM criteria_reference")
    ).fetchall()
    criteria_map = {row[1]: row[0] for row in criteria_rows}

    criteria_id = criteria_map.get("EB2_NIW_C2")
    section_id = section_map.get("background")

    if criteria_id and section_id:
        conn.execute(
            text(
                "DELETE FROM criteria_section_affinity_defaults "
                "WHERE criteria_id = :cid AND section_affinity_id = :sid "
                "AND visa_type = 'EB2' AND priority = 3"
            ),
            {"cid": criteria_id, "sid": section_id},
        )
