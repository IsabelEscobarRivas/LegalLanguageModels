"""Append KB style guidance instruction to active EB2 system prompts.

Revision ID: 0013_kb_guidance_prompt_instruction
Revises: 0012_nullable_case_id
Create Date: 2026-05-27

Appends rhetorical-conditioning instruction to all active EB2 system prompts.
Does not replace existing system prompt text.
"""
from alembic import op
from sqlalchemy import text

revision = "0013_kb_guidance_prompt_inst"
down_revision = "0012_nullable_case_id"
branch_labels = None
depends_on = None

STYLE_GUIDANCE_INSTRUCTION = """

IMPORTANT: If style guidance is provided below in a [KB STYLE GUIDANCE] block,
it is for rhetorical conditioning only. It must not be cited as evidence,
attributed to the petitioner, or presented as factual support for any claim.
Evidence is provided separately in the Evidence block and is the only permitted
source of factual claims in this section."""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "UPDATE prompt_templates "
        "SET system_prompt = system_prompt || :instruction "
        "WHERE visa_type = 'EB2' AND is_active = true "
        "AND system_prompt NOT LIKE '%%rhetorical conditioning%%'"
    ), {"instruction": STYLE_GUIDANCE_INSTRUCTION})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "UPDATE prompt_templates "
        "SET system_prompt = REPLACE(system_prompt, :instruction, '') "
        "WHERE visa_type = 'EB2'"
    ), {"instruction": STYLE_GUIDANCE_INSTRUCTION})
