"""KB template extraction pipeline — RAG 2 layer.

Reads kb_chunks, calls LLM to extract rhetorical scaffolds with evidence
placeholders, writes KBTemplate rows. Never raises.
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import openai
from sqlalchemy.orm import Session

from app.core.models import KBChunk, KBTemplate

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT_VERSION = "1.0"
EXTRACTION_MODEL = os.environ.get("GENERATION_MODEL", "gpt-4o")

SECTION_EXTRACTION_PROMPTS = {
    "introduction": "Extract the reusable Introduction drafting pattern. Preserve rhetorical sequence, formal opening, petition identification, preview of Dhanasar prongs. Replace all facts with placeholders such as [EVIDENCE: petitioner identity], [EVIDENCE: proposed endeavor], [EVIDENCE: prong summary].",
    "statement_of_law": "Extract the reusable Statement of Law structure. Preserve legal-standard sequencing, statutory references, Dhanasar framing, and preponderance framing. Do not use petitioner-specific facts.",
    "advanced_degree_qualification": "Extract the reusable Advanced Degree Qualification structure. Preserve sequencing around degree, credential evaluation, progressive experience, and nexus to endeavor. Replace facts with placeholders.",
    "prong1_endeavor_description": "Extract the reusable Proposed Endeavor Description structure. Preserve sequence for describing what the petitioner will do, focus areas, delivery model, and national need. Replace facts with placeholders.",
    "prong1_substantial_merit": "Extract the reusable Substantial Merit structure. Preserve framing around field importance, documented priorities, and why the endeavor has merit. Replace facts with placeholders.",
    "prong1_national_importance_welfare": "Extract the reusable Societal Welfare structure. Preserve national-scale need, public welfare framing, and evidence categories. Replace facts with placeholders.",
    "prong1_national_importance_initiative": "Extract the reusable Federal Initiative structure. Preserve sequence for federal programs, initiatives, national policy alignment, and petitioner connection. Replace facts with placeholders.",
    "prong2_educational_background": "Extract the reusable Educational Background structure. Preserve sequence around degrees, coursework, credential evaluations, and relevance to endeavor. Replace facts with placeholders.",
    "prong2_certifications_licensure": "Extract the reusable Certifications and Licensure structure. Preserve sequencing around certification, issuing body, date, significance, and professional relevance. Replace facts with placeholders.",
    "prong2_professional_experience": "Extract the reusable Professional Experience structure. Preserve role-by-role sequencing, title/employer/date progression, responsibility framing, and achievement placement. Replace facts with placeholders.",
    "prong2_professional_memberships": "Extract the reusable Professional Memberships structure. Preserve organization/significance/selectivity sequencing. Replace facts with placeholders.",
    "prong2_lectures_presentations": "Extract the reusable Lectures and Presentations structure. Preserve sequencing around venue, publication, contribution, audience, and significance. Replace facts with placeholders.",
    "prong2_peer_recognition": "Extract the reusable Recognition by Peers structure. Preserve sequence around recommender credibility, relationship, attestation, and significance framing. Replace facts with placeholders.",
    "prong2_expert_opinion_base": "Extract the reusable Expert Opinion structure. Preserve sequencing for expert introduction, credentials, opinion framing, and prong support structure. Replace facts with placeholders.",
    "prong3_endeavor_flexibility": "Extract the reusable Endeavor Flexibility structure. Preserve framing around cross-institutional, multi-site, or self-directed work. Replace facts with placeholders.",
    "prong3_public_interest": "Extract the reusable Public Interest structure. Preserve sequencing around urgency, public benefit, and waiver justification. Replace facts with placeholders.",
    "prong3_labor_market_shortage": "Extract the reusable Labor Market Shortage structure. Preserve sequencing around shortage evidence, projections, talent gaps, and petitioner fit. Replace facts with placeholders.",
    "prong3_no_adverse_effect": "Extract the reusable No Adverse Effect structure. Preserve framing that petitioner fills a gap rather than displacing US workers. Replace facts with placeholders.",
    "prong3_economic_benefit": "Extract the reusable Economic Benefit structure. Preserve sequencing around economic value, business benefit, compliance benefit, and national impact. Replace facts with placeholders.",
    "petition_conclusion": "Extract the reusable Conclusion structure. Preserve sequencing asserting all three Dhanasar prongs, preponderance standard, and formal request for approval. Replace facts with placeholders.",
}

EXTRACTION_SYSTEM_PROMPT = """You are a legal petition style and structure extractor for US immigration petitions.

Analyze the provided petition text and extract its reusable drafting structure for the given section.

Rules:
- Replace ALL case-specific facts with evidence placeholders like [EVIDENCE: description]
- Preserve rhetorical sequence, sentence cadence, and persuasive framing
- Never copy names, dates, institutions, metrics, or achievements
- Never treat the text as factual evidence
- Output ONLY valid JSON — no preamble, no markdown

Output JSON with this exact structure:
{
  "template_text": "The full abstracted template with [EVIDENCE: ...] placeholders",
  "evidence_placeholders": ["list of placeholder descriptions"],
  "argument_sequence": ["step 1 description", "step 2 description", ...],
  "tone_guidance": "Brief description of tone and rhetorical approach",
  "confidence": 0.0 to 1.0
}"""


def extract_kb_template(
    db: Session,
    kb_chunk_id: str,
    firm_id: str,
    visa_type: str,
    section_key: str,
) -> dict:
    """Extract a rhetorical template from a kb_chunk and persist as KBTemplate.

    Never raises. Returns status dict.
    """
    try:
        chunk = (
            db.query(KBChunk)
            .filter(KBChunk.id == kb_chunk_id, KBChunk.firm_id == firm_id)
            .first()
        )
        if chunk is None:
            return {"status": "failed", "reason": "chunk_not_found"}

        section_prompt = SECTION_EXTRACTION_PROMPTS.get(section_key)
        if section_prompt is None:
            return {"status": "failed", "reason": "unsupported_section_key"}

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"status": "failed", "reason": "missing_api_key"}

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=EXTRACTION_MODEL,
            temperature=0.0,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"SECTION: {section_key}\n"
                        f"SECTION DESCRIPTION: {section_prompt}\n\n"
                        f"KB TEXT TO ABSTRACT:\n{chunk.text}"
                    ),
                },
            ],
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as json_exc:
            logger.error(
                "extract_kb_template JSON parse failed chunk=%s: %s",
                kb_chunk_id, json_exc,
            )
            return {"status": "failed", "reason": "json_parse_failed"}

        template = KBTemplate(
            id=str(uuid.uuid4()),
            kb_chunk_id=kb_chunk_id,
            firm_id=firm_id,
            visa_type=visa_type,
            section_key=section_key,
            template_text=parsed.get("template_text", ""),
            evidence_placeholders=parsed.get("evidence_placeholders"),
            argument_sequence=parsed.get("argument_sequence"),
            tone_guidance=parsed.get("tone_guidance"),
            confidence=parsed.get("confidence"),
            extraction_prompt_version=EXTRACTION_PROMPT_VERSION,
            created_at=datetime.utcnow(),
        )
        db.add(template)
        db.commit()

        return {
            "status": "ok",
            "kb_template_id": template.id,
            "section_key": section_key,
            "confidence": template.confidence,
        }

    except Exception as exc:
        logger.exception(
            "extract_kb_template failed chunk=%s section=%s",
            kb_chunk_id, section_key,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "failed", "reason": str(exc)}
