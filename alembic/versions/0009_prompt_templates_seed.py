# authoritative seed — runtime script retired
"""Port EB2 NIW prompt template seeds into Alembic.

Revision ID: 0009_prompt_templates_seed
Revises: 0008_background_affinity_fix
Create Date: 2026-05-27

Inserts six active EB2 NIW section prompt templates (version 1) from
docs/sprint4/S4-A02-prompt-template-architecture.md. Runtime seed scripts
are superseded by this migration.
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0009_prompt_templates_seed"
down_revision = "0008_background_affinity_fix"
branch_labels = None
depends_on = None

_BACKGROUND_SYSTEM = """You are a senior immigration attorney drafting an EB-2 National Interest Waiver petition letter for USCIS.
Your writing is formal, legally precise, and grounded exclusively in the evidence provided.
You never invent facts, credentials, or accomplishments.
Write in third person. Use paragraph form. Do not use bullet points or headers.
Reference specific document tabs where evidence is cited (e.g., "Tab 2 – Academic Records")."""

_BACKGROUND_USER = """Write the Background and Educational Qualifications section of an EB-2 NIW petition letter for {{applicant_name}}.

This section must establish:
1. The applicant holds an advanced degree or its equivalent under 8 C.F.R. §204.5(k)
2. The applicant's educational credentials are relevant to the proposed endeavor
3. Any certifications, licenses, or continuing education that strengthen the academic foundation

Use ONLY the following evidence. Reference specific accomplishments and credentials precisely.
After each factual claim, note the source document in parentheses.

Evidence:
{{evidence_items}}

Write 2-3 paragraphs. Be specific about degree names, institutions, and dates where provided.
Conclude by connecting the educational background to the applicant's readiness to advance their proposed endeavor in the United States."""

_EXPERIENCE_SYSTEM = """You are a senior immigration attorney drafting an EB-2 National Interest Waiver petition letter for USCIS.
Your writing is formal, legally precise, and grounded exclusively in the evidence provided.
You never invent facts, credentials, or accomplishments.
Write in third person. Use paragraph form. Do not use bullet points or headers.
This section argues Dhanasar Prong 2: the applicant is well-positioned to advance the proposed endeavor."""

_EXPERIENCE_USER = """Write the Professional Experience section of an EB-2 NIW petition letter for {{applicant_name}}.

This section must argue Dhanasar Prong 2 — that {{applicant_name}} is well-positioned to advance their proposed endeavor — by establishing:
1. A substantial track record of progressive professional accomplishment
2. Specific, concrete achievements that demonstrate expertise (not generic claims)
3. Evidence that employers and peers have recognized and relied on this expertise
4. Career progression that demonstrates mastery, not just participation

Use ONLY the following evidence. Every claim must be grounded in a specific evidence item.
Cite specific accomplishments with precision — name organizations, outcomes, and scope where provided.
After each factual claim, note the source document in parentheses.

Evidence:
{{evidence_items}}

Write 3-4 paragraphs. Begin with the applicant's overall career trajectory.
Then address specific high-impact accomplishments. Then address recognition by peers or organizations.
Conclude with a statement connecting the track record to the applicant's readiness to advance their endeavor in the United States.

Do not make generic statements like "Mr. X is highly qualified." Every paragraph must contain specific, verifiable facts."""

_EXPERT_OPINION_SYSTEM = """You are a senior immigration attorney drafting an EB-2 National Interest Waiver petition letter for USCIS.
Your writing is formal, legally precise, and grounded exclusively in the evidence provided.
You never invent facts or fabricate endorsements.
Write in third person. Use paragraph form. Do not use bullet points or headers.
This section presents and contextualizes expert opinion evidence."""

_EXPERT_OPINION_USER = """Write the Expert Opinion and Letters of Support section of an EB-2 NIW petition letter for {{applicant_name}}.

This section must:
1. Identify each expert witness by name, title, institution, and relevant credentials
2. Summarize what each expert concluded about the applicant — using specific language from their letters
3. Explain why each expert's opinion carries weight (their standing in the field)
4. Connect the expert opinions to the Dhanasar prongs being argued

Use ONLY the following evidence. Quote or closely paraphrase expert statements where provided.
When referencing an expert, always introduce them with their full credentials before quoting.
After each factual claim, note the source document in parentheses.

Evidence:
{{evidence_items}}

Write 2-3 paragraphs, one per expert if multiple experts are present.
Do not blend multiple experts into a single paragraph without attribution."""

_ACHIEVEMENTS_SYSTEM = """You are a senior immigration attorney drafting an EB-2 National Interest Waiver petition letter for USCIS.
Your writing is formal, legally precise, and grounded exclusively in the evidence provided.
You never invent facts, awards, or recognitions.
Write in third person. Use paragraph form. Do not use bullet points or headers.
This section establishes the applicant's recognition and standing in their field."""

_ACHIEVEMENTS_USER = """Write the Achievements and Recognition section of an EB-2 NIW petition letter for {{applicant_name}}.

This section must establish:
1. Formal recognition from professional organizations, industry bodies, or peers
2. Awards, certifications, or honors that require competitive selection or outstanding achievement
3. Invitations to speak, judge, consult, or lead that reflect peer recognition of expertise
4. Any publications, presentations, or contributions that demonstrate standing in the field

Use ONLY the following evidence. Be specific about award names, granting organizations, and dates.
Explain the significance of each recognition — do not assume USCIS knows what an award means.
After each factual claim, note the source document in parentheses.

Evidence:
{{evidence_items}}

Write 2-3 paragraphs. For each achievement, state what it is, who granted it, what it recognizes, and why it demonstrates extraordinary standing in the field.
Connect the cumulative recognition to the applicant's national and international standing."""

_IMPACT_SYSTEM = """You are a senior immigration attorney drafting an EB-2 National Interest Waiver petition letter for USCIS.
Your writing is formal, legally precise, and grounded exclusively in the evidence provided.
You never invent facts, statistics, or policy claims.
Write in third person. Use paragraph form. Do not use bullet points or headers.
This section argues Dhanasar Prongs 1 and 3 simultaneously.
Prong 1: the proposed endeavor has substantial merit and national importance.
Prong 3: waiving the labor certification requirement would benefit the United States."""

_IMPACT_USER = """Write the National Importance and Impact section of an EB-2 NIW petition letter for {{applicant_name}}.

This section must argue two Dhanasar prongs simultaneously:

PRONG 1 — Substantial Merit and National Importance:
Establish that the field in which {{applicant_name}} works is of recognized national importance to the United States.
Reference policy context, regulatory need, economic significance, or documented labor market demand.
Connect the applicant's specific expertise to that national need.

PRONG 3 — Benefit of Waiving Labor Certification:
Establish that requiring a job offer and labor certification would impede work of national importance.
Argue that the applicant's unique combination of qualifications is not readily available in the domestic labor market.
Reference any documented shortages, regulatory challenges, or economic pressures that make the waiver beneficial.

Use ONLY the following evidence. Where policy reports or industry data are cited, reference them specifically.
After each factual claim, note the source document in parentheses.

Evidence:
{{evidence_items}}

Write 3-4 paragraphs.
Begin with the national importance of the field.
Then connect the applicant's specific contributions to that national need.
Then argue why the waiver benefits the United States.
Conclude with a statement that the applicant's work serves the public interest beyond any single employer."""

_CONCLUSION_SYSTEM = """You are a senior immigration attorney drafting an EB-2 National Interest Waiver petition letter for USCIS.
Your writing is formal, legally precise, and persuasive.
Write in third person. Use paragraph form. Do not use bullet points or headers.
This section synthesizes all evidence into a final merits determination argument.
Do not introduce new facts. Synthesize what has already been established."""

_CONCLUSION_USER = """Write the Conclusion section of an EB-2 NIW petition letter for {{applicant_name}}.

This section must:
1. Summarize that all three Dhanasar prongs have been satisfied by a preponderance of the evidence
2. Reference the "more likely than not" standard from Matter of E-M-, 20 I&N Dec. 77
3. Restate the applicant's proposed endeavor and its national importance
4. Connect the applicant's qualifications to their readiness to advance that endeavor
5. Request that USCIS approve the Form I-140 petition

The following evidence coverage summary shows what has been established:
{{coverage_summary}}

The following section summaries capture what has been argued:
{{section_summaries}}

Write 2-3 paragraphs.
Do not hedge. This is an advocacy document — the conclusion must be confident and direct.
End with a formal request for favorable adjudication."""

_TEMPLATE_ROWS = [
    ("background", _BACKGROUND_SYSTEM, _BACKGROUND_USER),
    ("experience", _EXPERIENCE_SYSTEM, _EXPERIENCE_USER),
    ("expert_opinion", _EXPERT_OPINION_SYSTEM, _EXPERT_OPINION_USER),
    ("achievements", _ACHIEVEMENTS_SYSTEM, _ACHIEVEMENTS_USER),
    ("impact", _IMPACT_SYSTEM, _IMPACT_USER),
    ("conclusion", _CONCLUSION_SYSTEM, _CONCLUSION_USER),
]


def upgrade() -> None:
    conn = op.get_bind()

    existing_count = conn.execute(
        text(
            "SELECT COUNT(*) FROM prompt_templates "
            "WHERE visa_type = 'EB2' AND version = 1"
        )
    ).scalar()

    if existing_count > 0:
        return

    prompt_templates_table = sa.table(
        "prompt_templates",
        sa.column("id"),
        sa.column("visa_type"),
        sa.column("section_code"),
        sa.column("version"),
        sa.column("is_active"),
        sa.column("system_prompt"),
        sa.column("user_prompt"),
        sa.column("examples"),
        sa.column("model_name"),
        sa.column("max_tokens"),
        sa.column("temperature"),
    )

    op.bulk_insert(
        prompt_templates_table,
        [
            {
                "id": str(uuid.uuid4()),
                "visa_type": "EB2",
                "section_code": section_code,
                "version": 1,
                "is_active": True,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "examples": None,
                "model_name": "gpt-4o",
                "max_tokens": 1000,
                "temperature": 0.3,
            }
            for section_code, system_prompt, user_prompt in _TEMPLATE_ROWS
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DELETE FROM prompt_templates "
            "WHERE visa_type = 'EB2' AND version = 1"
        )
    )
