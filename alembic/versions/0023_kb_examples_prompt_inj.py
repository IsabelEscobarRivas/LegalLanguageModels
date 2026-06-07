"""Inject {{kb_examples}} block into prompt_templates user_prompts.

Revision ID: 0023_kb_examples_prompt_inj
Revises: 0020_petition_prompt_templates
Create Date: 2026-06-07

Adds [KB STYLE GUIDANCE] block with {{kb_examples}} before Evidence blocks
in evidence-grounded sections, and before Coverage summary in conclusion
and petition_conclusion.
"""
from alembic import op
from sqlalchemy import text


revision = "0023_kb_examples_prompt_inj"
down_revision = "0020_petition_prompt_templates"
branch_labels = None
depends_on = None

KB_GUIDANCE_BLOCK = (
    "[KB STYLE GUIDANCE]\n"
    "Use the following excerpts from this firm's successful petitions and style "
    "guides to condition the tone, structure, and rhetorical approach of your "
    "response. Do not cite these as evidence or attribute them to the petitioner.\n\n"
    "{{kb_examples}}\n\n"
)

EVIDENCE_MARKER = "Evidence:\n{{evidence_items}}"
EVIDENCE_WITH_KB = KB_GUIDANCE_BLOCK + EVIDENCE_MARKER

COVERAGE_MARKER = "Coverage summary:\n{{coverage_summary}}"
COVERAGE_WITH_KB = KB_GUIDANCE_BLOCK + COVERAGE_MARKER


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE prompt_templates "
            "SET user_prompt = REPLACE(user_prompt, :old, :new) "
            "WHERE user_prompt LIKE '%Evidence:%{{evidence_items}}%' "
            "AND user_prompt NOT LIKE '%{{kb_examples}}%'"
        ),
        {"old": EVIDENCE_MARKER, "new": EVIDENCE_WITH_KB},
    )
    conn.execute(
        text(
            "UPDATE prompt_templates "
            "SET user_prompt = REPLACE(user_prompt, :old, :new) "
            "WHERE section_code IN ('conclusion', 'petition_conclusion') "
            "AND user_prompt NOT LIKE '%{{kb_examples}}%'"
        ),
        {"old": COVERAGE_MARKER, "new": COVERAGE_WITH_KB},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE prompt_templates "
            "SET user_prompt = REPLACE(user_prompt, :new, :old) "
            "WHERE user_prompt LIKE '%{{kb_examples}}%' "
            "AND user_prompt LIKE '%Evidence:%{{evidence_items}}%'"
        ),
        {"old": EVIDENCE_MARKER, "new": EVIDENCE_WITH_KB},
    )
    conn.execute(
        text(
            "UPDATE prompt_templates "
            "SET user_prompt = REPLACE(user_prompt, :new, :old) "
            "WHERE section_code IN ('conclusion', 'petition_conclusion') "
            "AND user_prompt LIKE '%{{kb_examples}}%'"
        ),
        {"old": COVERAGE_MARKER, "new": COVERAGE_WITH_KB},
    )
