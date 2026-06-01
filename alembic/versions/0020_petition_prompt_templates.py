"""Seed EB-2 NIW petition prompt templates for new section architecture.

Revision ID: 0020_petition_prompt_templates
Revises: 0019_petition_section_taxonomy
Create Date: 2026-06-01

Inserts 20 active EB2 NIW prompt templates (version 1) for the Dhanasar
prong hierarchy. Original 6 templates are preserved.
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "0020_petition_prompt_templates"
down_revision = "0019_petition_section_taxonomy"
branch_labels = None
depends_on = None


KB_INSTRUCTION = """

IMPORTANT: If style guidance is provided below in a [KB STYLE GUIDANCE] block,
it is for rhetorical conditioning only. It must not be cited as evidence,
attributed to the petitioner, or presented as factual support for any claim.
Evidence is provided separately in the Evidence block and is the only permitted
source of factual claims in this section."""


NEW_SECTION_CODES = [
    "introduction",
    "statement_of_law",
    "advanced_degree_qualification",
    "prong1_endeavor_description",
    "prong1_substantial_merit",
    "prong1_national_importance_welfare",
    "prong1_national_importance_initiative",
    "prong2_educational_background",
    "prong2_certifications_licensure",
    "prong2_lectures_presentations",
    "prong2_professional_experience",
    "prong2_professional_memberships",
    "prong2_peer_recognition",
    "prong2_expert_opinion_base",
    "prong3_endeavor_flexibility",
    "prong3_public_interest",
    "prong3_labor_market_shortage",
    "prong3_no_adverse_effect",
    "prong3_economic_benefit",
    "petition_conclusion",
]


def _system(base: str) -> str:
    return base + KB_INSTRUCTION


_TEMPLATE_ROWS = [
    {
        "section_code": "introduction",
        "prong_number": None,
        "word_count_min": 400,
        "word_count_max": 600,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 National Interest "
            "Waiver petition letter for USCIS. Your writing is formal, legally precise, "
            "and persuasive. Write in third person. Use paragraph form. Do not use "
            "bullet points or headers. This section opens the petition and frames all "
            "three Dhanasar prongs that will be argued."
        ),
        "user_prompt": (
            "Write the Introduction of an EB-2 NIW petition letter for {{applicant_name}}.\n\n"
            "This section must:\n"
            "1. Address USCIS formally and identify the petition type (Form I-140, "
            "EB-2 National Interest Waiver, INA §203(b)(2)(A), 8 CFR §204.5(k))\n"
            "2. State the petitioner's field and proposed endeavor in one clear sentence\n"
            "3. Assert that the evidence demonstrates all three Dhanasar prongs are satisfied\n"
            "4. Briefly preview the structure of the petition\n\n"
            "Use ONLY the following evidence.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 3-4 paragraphs. Be direct and confident. End by stating that the "
            "evidence comprehensively establishes eligibility for the National Interest Waiver."
        ),
    },
    {
        "section_code": "statement_of_law",
        "prong_number": None,
        "word_count_min": 300,
        "word_count_max": 500,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally and precisely. This section states the legal framework "
            "only. Do not discuss the petitioner's facts here."
        ),
        "user_prompt": (
            "Write the Statement of the Law section for an EB-2 NIW petition.\n\n"
            "This section must:\n"
            "1. Cite INA §203(b)(2)(A) and the visa category definition\n"
            "2. Define 'advanced degree' under 8 C.F.R. §204.5(k)(2) verbatim\n"
            "3. Explain the Dhanasar framework (Matter of Dhanasar, 26 I&N Dec. 884, "
            "AAO 2016) and its three-prong test\n"
            "4. State the preponderance of evidence standard ('more likely than not')\n\n"
            "Write 2-3 paragraphs. Be precise and formal. Do not mention the "
            "petitioner by name in this section."
        ),
    },
    {
        "section_code": "advanced_degree_qualification",
        "prong_number": None,
        "word_count_min": 800,
        "word_count_max": 1200,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Your writing is formal, legally precise, and grounded exclusively "
            "in the evidence provided. You never invent credentials or accomplishments. "
            "Write in third person. Use paragraph form."
        ),
        "user_prompt": (
            "Write the Advanced Degree Qualification section for {{applicant_name}}.\n\n"
            "This section must establish:\n"
            "1. The specific degrees held: name, institution, country, year\n"
            "2. If a foreign degree: cite the credential evaluation establishing US equivalency\n"
            "3. Years of progressive professional experience if used to establish equivalency\n"
            "4. Direct nexus between the advanced degree and the proposed endeavor\n"
            "5. Comparison showing petitioner exceeds the US labor market minimum "
            "qualifications for this occupation\n\n"
            "Use ONLY the following evidence. Be specific about degree names, "
            "institutions, dates, and evaluation conclusions.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 4-5 paragraphs. Conclude by affirming that petitioner clearly "
            "satisfies 8 C.F.R. §204.5(k) as a Professional Holding an Advanced Degree."
        ),
    },
    {
        "section_code": "prong1_endeavor_description",
        "prong_number": 1,
        "word_count_min": 400,
        "word_count_max": 600,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section describes the petitioner's proposed "
            "endeavor in the United States. Ground every claim in the evidence provided. "
            "You never invent facts."
        ),
        "user_prompt": (
            "Write the Proposed Endeavor Description for {{applicant_name}}.\n\n"
            "This section must:\n"
            "1. State clearly what the petitioner will do in the United States\n"
            "2. Identify 3-5 specific focus areas or work streams\n"
            "3. Explain how the work will be delivered\n"
            "4. Connect the endeavor to a documented national need\n\n"
            "Use ONLY the following evidence.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 3-4 paragraphs. Be specific and concrete. Avoid generic claims."
        ),
    },
    {
        "section_code": "prong1_substantial_merit",
        "prong_number": 1,
        "word_count_min": 800,
        "word_count_max": 1200,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section argues that the petitioner's field "
            "and proposed endeavor have substantial merit. Use external source evidence "
            "alongside petitioner evidence. You never invent facts or statistics."
        ),
        "user_prompt": (
            "Write the Substantial Merit section for {{applicant_name}}'s EB-2 NIW petition.\n\n"
            "This section must establish that the proposed endeavor has substantial merit by:\n"
            "1. Identifying the field's recognized importance via professional association "
            "priorities, federal investment, or policy recognition\n"
            "2. Connecting specific focus areas of the endeavor to documented field priorities\n"
            "3. Explaining why each focus area advances the scientific, economic, or "
            "social foundation of the field\n\n"
            "Cite external sources (reports, agency priorities, industry publications) "
            "where provided alongside petitioner evidence.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 4-5 paragraphs. Each paragraph must make a specific substantiated "
            "claim — not a generic assertion."
        ),
    },
    {
        "section_code": "prong1_national_importance_welfare",
        "prong_number": 1,
        "word_count_min": 600,
        "word_count_max": 900,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section establishes national importance by "
            "showing the petitioner's work broadly enhances societal welfare. You never "
            "invent facts, statistics, or policy claims."
        ),
        "user_prompt": (
            "Write the National Importance — Societal Welfare section for {{applicant_name}}.\n\n"
            "This section must:\n"
            "1. Document the national scale of the problem or need the petitioner addresses\n"
            "2. Cite federal agency findings on population impact, economic burden, "
            "or health or security disparities\n"
            "3. Show how the petitioner's specific work addresses those documented needs\n"
            "4. Connect the endeavor to equity, access, economic productivity, or security\n\n"
            "Cite external sources prominently. Every paragraph must cite at least "
            "one external source establishing the national scale of need.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 4-5 paragraphs."
        ),
    },
    {
        "section_code": "prong1_national_importance_initiative",
        "prong_number": 1,
        "word_count_min": 700,
        "word_count_max": 1000,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section ties the petitioner's work directly "
            "to specific named federal programs, executive orders, or agency strategic "
            "plans. You never invent policy claims."
        ),
        "user_prompt": (
            "Write the National Importance — Federal Initiative section for {{applicant_name}}.\n\n"
            "This section must:\n"
            "1. Identify specific named federal programs or initiatives relevant to "
            "the petitioner's field\n"
            "2. For each initiative: state what it calls for and how the petitioner's "
            "work advances it specifically\n"
            "3. Show that the petitioner's endeavor directly responds to federal priorities\n\n"
            "Name each federal initiative explicitly.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 3-4 paragraphs, one major federal initiative per paragraph where possible."
        ),
    },
    {
        "section_code": "prong2_educational_background",
        "prong_number": 2,
        "word_count_min": 400,
        "word_count_max": 600,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section establishes the petitioner's educational "
            "qualifications under Prong 2. You never invent credentials."
        ),
        "user_prompt": (
            "Write the Educational Background section for {{applicant_name}} under Prong 2.\n\n"
            "This section must:\n"
            "1. Identify each degree: full name, institution, country, year, specialization\n"
            "2. Describe relevant coursework that directly supports the proposed endeavor\n"
            "3. Note any credential evaluations establishing US equivalency\n"
            "4. Connect the educational foundation to the petitioner's readiness to "
            "advance the proposed endeavor\n\n"
            "Be specific — name courses, specializations, and thesis topics where provided.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 2-3 paragraphs."
        ),
    },
    {
        "section_code": "prong2_certifications_licensure",
        "prong_number": 2,
        "word_count_min": 400,
        "word_count_max": 600,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section establishes the petitioner's professional "
            "certifications and licenses as evidence of exceptional ability. You never "
            "invent credentials or pass rates."
        ),
        "user_prompt": (
            "Write the Certifications and Licensure section for {{applicant_name}} under Prong 2.\n\n"
            "For each credential:\n"
            "1. Name the certification or license, issuing body, and date\n"
            "2. Explain what the credential certifies and why it is significant\n"
            "3. Note any selectivity, pass rates, or competitive requirements where in evidence\n"
            "4. Connect it to the proposed endeavor\n\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 2-4 paragraphs. Do not list credentials without explaining their "
            "significance."
        ),
    },
    {
        "section_code": "prong2_lectures_presentations",
        "prong_number": 2,
        "word_count_min": 400,
        "word_count_max": 600,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section establishes the petitioner's standing "
            "in the field through published work, lectures, and conference presentations. "
            "You never invent venues, publications, or quotes."
        ),
        "user_prompt": (
            "Write the Lectures, Presentations, and Scientific Contributions section "
            "for {{applicant_name}} under Prong 2.\n\n"
            "For each contribution:\n"
            "1. Name the venue, conference, or publication\n"
            "2. Describe what was presented or published\n"
            "3. Explain the significance of the venue and the audience reached\n"
            "4. Connect it to the petitioner's standing in the field\n\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 3-4 paragraphs. If no lecture or publication evidence is present, "
            "return the sentinel: INSUFFICIENT EVIDENCE — no publications or presentations "
            "classified for this section."
        ),
    },
    {
        "section_code": "prong2_professional_experience",
        "prong_number": 2,
        "word_count_min": 1000,
        "word_count_max": 1500,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section argues Prong 2 through a role-by-role "
            "account of the petitioner's progressive professional accomplishments. Every "
            "claim must be specific and grounded in evidence. You never generalize or "
            "invent facts."
        ),
        "user_prompt": (
            "Write the Professional Experience section for {{applicant_name}} under Prong 2.\n\n"
            "For each role:\n"
            "1. State: title, employer, dates\n"
            "2. Describe specific responsibilities with precision\n"
            "3. Identify specific achievements and measurable outcomes\n"
            "4. Show progressive advancement in responsibility and recognition\n\n"
            "End with a synthesis paragraph arguing that the career trajectory "
            "demonstrates exceptional ability and readiness to advance the proposed "
            "endeavor.\n\n"
            "Name organizations, outcomes, and scope precisely.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 4-6 paragraphs. Every paragraph must contain specific verifiable "
            "facts — no generic statements."
        ),
    },
    {
        "section_code": "prong2_professional_memberships",
        "prong_number": 2,
        "word_count_min": 300,
        "word_count_max": 500,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section establishes professional memberships "
            "as evidence of standing and recognition in the field."
        ),
        "user_prompt": (
            "Write the Professional Memberships section for {{applicant_name}} under Prong 2.\n\n"
            "For each membership:\n"
            "1. Name the organization and its mission\n"
            "2. Describe the significance of membership — size, selectivity, global standing\n"
            "3. Explain what the membership provides\n"
            "4. Connect membership to the petitioner's standing in the field\n\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 2-3 paragraphs."
        ),
    },
    {
        "section_code": "prong2_peer_recognition",
        "prong_number": 2,
        "word_count_min": 600,
        "word_count_max": 900,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section presents recognition from peers and "
            "industry leaders as independent third-party validation. You never invent "
            "quotes or attribute statements not present in the evidence."
        ),
        "user_prompt": (
            "Write the Recognition by Peers and Industry Leaders section for "
            "{{applicant_name}} under Prong 2.\n\n"
            "For each letter of support:\n"
            "1. Identify the author: name, title, institution, years of experience\n"
            "2. Describe the author's relationship to the petitioner\n"
            "3. Summarize what the author specifically attests\n"
            "4. Explain why this author's recognition carries weight\n\n"
            "Conclude by noting the pattern of independent recognition across "
            "multiple sources. Always introduce an author fully before quoting them.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 3-5 paragraphs, one per support letter author where possible."
        ),
    },
    {
        "section_code": "prong2_expert_opinion_base",
        "prong_number": 2,
        "word_count_min": 600,
        "word_count_max": 900,
        "is_dynamic": True,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section presents a single expert opinion letter. "
            "You never invent facts, credentials, or quotes. Every claim must come from "
            "the evidence provided. Introduce the expert fully before quoting them."
        ),
        "user_prompt": (
            "Write the Expert Opinion section for {{applicant_name}} based on the "
            "opinion of {{expert_name}}.\n\n"
            "This section must:\n"
            "1. Introduce {{expert_name}}: full name, title, institution, relevant "
            "qualifications, and why they are qualified to opine\n"
            "2. State what the expert was asked to evaluate\n"
            "3. Present the expert's assessment of Prong 1 where addressed\n"
            "4. Present the expert's assessment of Prong 2 where addressed\n"
            "5. Present the expert's assessment of Prong 3 where addressed\n"
            "6. Quote the expert's most probative conclusions with source citation\n\n"
            "Never attribute quotes or credentials not present in the evidence.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 3-4 paragraphs."
        ),
    },
    {
        "section_code": "prong3_endeavor_flexibility",
        "prong_number": 3,
        "word_count_min": 400,
        "word_count_max": 600,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section argues that the nature of the proposed "
            "endeavor requires flexibility that a fixed employer-employee relationship "
            "cannot provide."
        ),
        "user_prompt": (
            "Write the Endeavor Flexibility section for {{applicant_name}} under Prong 3.\n\n"
            "This section must argue that:\n"
            "1. The proposed work is cross-institutional, multi-site, or self-directed\n"
            "2. A PERM-anchored role at a single employer would constrain the endeavor\n"
            "3. The work requires collaborations with multiple institutions simultaneously\n"
            "4. Waiving the job offer requirement enables the work\n\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 2-3 paragraphs."
        ),
    },
    {
        "section_code": "prong3_public_interest",
        "prong_number": 3,
        "word_count_min": 400,
        "word_count_max": 600,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section argues that immediate execution of "
            "the endeavor serves the public interest more than the benefit of labor "
            "certification. You never invent facts or policy claims."
        ),
        "user_prompt": (
            "Write the Public Interest section for {{applicant_name}} under Prong 3.\n\n"
            "This section must argue:\n"
            "1. The public benefit of allowing the petitioner to proceed without delay\n"
            "2. What is lost in national benefit if labor certification is required\n"
            "3. The time cost of the PERM process relative to the urgency of the need\n"
            "4. Why the benefits of granting the waiver outweigh the advantages of "
            "the labor certification process\n\n"
            "Use ONLY the following evidence.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 2-3 paragraphs."
        ),
    },
    {
        "section_code": "prong3_labor_market_shortage",
        "prong_number": 3,
        "word_count_min": 500,
        "word_count_max": 700,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section establishes a documented shortage of "
            "qualified professionals in the petitioner's field using external source "
            "data. You never invent statistics."
        ),
        "user_prompt": (
            "Write the Labor Market Shortage section for {{applicant_name}} under Prong 3.\n\n"
            "This section must establish:\n"
            "1. A documented national shortage of qualified professionals in this field\n"
            "2. Open position data, demand projections, and talent gap statistics\n"
            "3. Government or industry acknowledgment of the shortage\n"
            "4. Why the petitioner's specialized qualifications are not readily available "
            "in the domestic labor market\n\n"
            "Cite external sources prominently (BLS, professional associations, "
            "government reports, industry studies).\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 3-4 paragraphs. Every paragraph must cite at least one external "
            "source establishing the shortage."
        ),
    },
    {
        "section_code": "prong3_no_adverse_effect",
        "prong_number": 3,
        "word_count_min": 300,
        "word_count_max": 500,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section argues that the petitioner will not "
            "displace US workers and will instead enhance the capacity of the existing "
            "workforce."
        ),
        "user_prompt": (
            "Write the No Adverse Effect on US Workers section for {{applicant_name}} "
            "under Prong 3.\n\n"
            "This section must argue:\n"
            "1. The petitioner fills a documented gap rather than displacing domestic workers\n"
            "2. The petitioner's work raises the productivity and effectiveness of "
            "existing US practitioners and institutions\n"
            "3. The endeavor creates value for the workforce rather than competing with it\n"
            "4. Government and policy sources acknowledging the need for professionals "
            "like the petitioner\n\n"
            "Use ONLY the following evidence.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 2-3 paragraphs."
        ),
    },
    {
        "section_code": "prong3_economic_benefit",
        "prong_number": 3,
        "word_count_min": 300,
        "word_count_max": 500,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally. This section establishes the economic benefit to "
            "the United States of granting the waiver. You never invent statistics "
            "or economic claims."
        ),
        "user_prompt": (
            "Write the Economic Benefit section for {{applicant_name}} under Prong 3.\n\n"
            "This section must establish:\n"
            "1. The economic value the petitioner's work will generate for the US\n"
            "2. The cost to the US economy of not granting the waiver\n"
            "3. Tax revenue, business growth, compliance benefit, or cost savings "
            "that result from the petitioner's work\n"
            "4. Any quantifiable economic impact data from external sources\n\n"
            "Use ONLY the following evidence.\n"
            "After each factual claim, note the source document in parentheses.\n\n"
            "Evidence:\n"
            "{{evidence_items}}\n\n"
            "Write 2-3 paragraphs."
        ),
    },
    {
        "section_code": "petition_conclusion",
        "prong_number": None,
        "word_count_min": 600,
        "word_count_max": 900,
        "is_dynamic": False,
        "system_prompt": _system(
            "You are a senior immigration attorney drafting an EB-2 NIW petition for "
            "USCIS. Write formally and persuasively. This section synthesizes all "
            "evidence into a final merits determination. Do not introduce new facts. "
            "Be confident and direct."
        ),
        "user_prompt": (
            "Write the Conclusion of an EB-2 NIW petition letter for {{applicant_name}}.\n\n"
            "This section must:\n"
            "1. Assert that all three Dhanasar prongs have been satisfied by a "
            "preponderance of the evidence\n"
            "2. Reference the 'more likely than not' standard from Matter of E-M-, "
            "20 I&N Dec. 77\n"
            "3. Restate the petitioner's proposed endeavor and its national importance\n"
            "4. Summarize the petitioner's qualifications and readiness to advance "
            "the endeavor\n"
            "5. Make a formal request for USCIS approval of Form I-140 and the "
            "National Interest Waiver\n\n"
            "Coverage summary:\n"
            "{{coverage_summary}}\n\n"
            "Section summaries:\n"
            "{{section_summaries}}\n\n"
            "Write 3-4 paragraphs. End with a formal confident request for "
            "favorable adjudication."
        ),
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    codes_sql = ", ".join(f"'{code}'" for code in NEW_SECTION_CODES)
    existing_count = conn.execute(
        text(
            f"SELECT COUNT(*) FROM prompt_templates "
            f"WHERE visa_type = 'EB2' AND version = 1 "
            f"AND section_code IN ({codes_sql})"
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
        sa.column("word_count_min"),
        sa.column("word_count_max"),
        sa.column("prong_number"),
        sa.column("is_dynamic"),
    )

    op.bulk_insert(
        prompt_templates_table,
        [
            {
                "id": str(uuid.uuid4()),
                "visa_type": "EB2",
                "section_code": row["section_code"],
                "version": 1,
                "is_active": True,
                "system_prompt": row["system_prompt"],
                "user_prompt": row["user_prompt"],
                "examples": None,
                "model_name": "gpt-4o",
                "max_tokens": 2000,
                "temperature": 0.3,
                "word_count_min": row["word_count_min"],
                "word_count_max": row["word_count_max"],
                "prong_number": row["prong_number"],
                "is_dynamic": row["is_dynamic"],
            }
            for row in _TEMPLATE_ROWS
        ],
    )


def downgrade() -> None:
    codes_sql = ", ".join(f"'{code}'" for code in NEW_SECTION_CODES)
    op.execute(
        text(
            f"DELETE FROM prompt_templates "
            f"WHERE visa_type = 'EB2' AND version = 1 "
            f"AND section_code IN ({codes_sql})"
        )
    )
