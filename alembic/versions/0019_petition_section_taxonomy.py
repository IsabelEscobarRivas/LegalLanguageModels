"""Petition section taxonomy expansion and prompt template metadata.

Revision ID: 0019_petition_section_taxonomy
Revises: 0018_reviewer_notes
Create Date: 2026-06-01

Adds NIW petition section codes to section_affinity_reference (alongside
the original 6). Extends prompt_templates with word count targets,
prong_number, and is_dynamic for Sprint 7.7.
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "0019_petition_section_taxonomy"
down_revision = "0018_reviewer_notes"
branch_labels = None
depends_on = None


NEW_SECTION_CODES = [
    # Introduction and Law
    "introduction",
    "statement_of_law",
    "advanced_degree_qualification",
    # Prong 1
    "prong1_endeavor_description",
    "prong1_substantial_merit",
    "prong1_national_importance_welfare",
    "prong1_national_importance_initiative",
    # Prong 2
    "prong2_educational_background",
    "prong2_certifications_licensure",
    "prong2_lectures_presentations",
    "prong2_professional_experience",
    "prong2_professional_memberships",
    "prong2_peer_recognition",
    # Prong 3
    "prong3_endeavor_flexibility",
    "prong3_public_interest",
    "prong3_labor_market_shortage",
    "prong3_no_adverse_effect",
    "prong3_economic_benefit",
    # Conclusion
    "petition_conclusion",
]


def _label_from_code(code: str) -> str:
    return code.replace("_", " ").title()


def upgrade() -> None:
    conn = op.get_bind()

    for display_order, code in enumerate(NEW_SECTION_CODES, start=7):
        label = _label_from_code(code)
        conn.execute(
            text(
                """
                INSERT INTO section_affinity_reference
                    (id, code, label, description, display_order)
                VALUES
                    (:id, :code, :label, :description, :display_order)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "code": code,
                "label": label,
                "description": f"Petition section: {label}",
                "display_order": display_order,
            },
        )

    op.add_column(
        "prompt_templates",
        sa.Column("word_count_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "prompt_templates",
        sa.Column("word_count_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "prompt_templates",
        sa.Column("prong_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "prompt_templates",
        sa.Column(
            "is_dynamic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("prompt_templates", "is_dynamic")
    op.drop_column("prompt_templates", "prong_number")
    op.drop_column("prompt_templates", "word_count_max")
    op.drop_column("prompt_templates", "word_count_min")

    codes_sql = ", ".join(f"'{code}'" for code in NEW_SECTION_CODES)
    op.execute(
        text(
            f"DELETE FROM section_affinity_reference WHERE code IN ({codes_sql})"
        )
    )
