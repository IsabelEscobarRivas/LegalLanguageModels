import logging
import os
from typing import Optional

import openai
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.models import PromptTemplate
from app.ingestion.embedder import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL


logger = logging.getLogger(__name__)


def get_active_template(
    db: Session,
    visa_type: str,
    section_code: str,
) -> Optional[PromptTemplate]:
    """Retrieve the active prompt template for a visa type and section.

    Priority:
    1. Exact visa_type match, highest version, is_active=True
    2. BOTH match, highest version, is_active=True
    3. None if no template found

    Returns None if no active template exists — caller must handle this
    as a 503 (generation cannot proceed without a template).
    """
    result = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.visa_type.in_([visa_type, "BOTH"]),
            PromptTemplate.section_code == section_code,
            PromptTemplate.is_active == True,
        )
        .order_by(
            PromptTemplate.visa_type.desc(),
            PromptTemplate.version.desc(),
        )
        .first()
    )
    if result is None:
        logger.warning(
            "No active prompt template found for visa_type=%s section_code=%s",
            visa_type,
            section_code,
        )
    return result


def render_prompt(
    template: PromptTemplate,
    variables: dict,
) -> tuple[str, str]:
    """Substitute {{variable}} placeholders in system and user prompts.

    Returns (rendered_system_prompt, rendered_user_prompt).
    Unknown variables are left as-is with a warning logged.
    Never raises.
    """
    import re

    def substitute(text: str, vars: dict) -> str:
        def replacer(match):
            key = match.group(1).strip()
            if key in vars:
                value = vars[key]
                if isinstance(value, list):
                    return "\n".join(
                        f"{i + 1}. {item}" for i, item in enumerate(value)
                    )
                return str(value) if value is not None else ""
            logger.warning("Prompt variable not found: %s", key)
            return match.group(0)

        return re.sub(r"\{\{([^}]+)\}\}", replacer, text)

    system = substitute(template.system_prompt, variables)
    user = substitute(template.user_prompt, variables)

    if template.examples and template.examples.strip():
        section_name = variables.get("section_name", "this section")
        examples_block = (
            f"Example of a strong {section_name}:\n"
            f"---\n{template.examples}\n---\n"
        )
        if "Evidence:" in user:
            user = user.replace("Evidence:", examples_block + "\nEvidence:")
        else:
            user = examples_block + "\n" + user

    return system, user


def get_kb_style_guidance(
    visa_type: str,
    section_code: str,
    evidence_summary: str,
    db: Optional[Session] = None,
    firm_id: Optional[str] = None,
) -> tuple[Optional[str], list[str]]:
    """Retrieve firm-scoped KB style guidance for a draft section.

    Returns (guidance_string, kb_chunk_ids). When db or firm_id is omitted,
    returns (None, []).
    """
    if db is None or firm_id is None:
        return (None, [])

    allowed_types_by_section = {
        # Legacy section codes
        "background": ["style_guide", "firm_convention", "precedent_letter"],
        "experience": ["style_guide", "firm_convention", "precedent_letter"],
        "achievements": ["style_guide", "firm_convention", "precedent_letter"],
        "expert_opinion": ["style_guide", "precedent_letter"],
        "impact": ["style_guide", "firm_convention", "precedent_letter"],
        "conclusion": ["style_guide", "firm_convention", "precedent_letter"],
        # NIW section codes
        "introduction": ["style_guide", "firm_convention", "precedent_letter"],
        "statement_of_law": ["style_guide", "firm_convention"],
        "advanced_degree_qualification": ["style_guide", "firm_convention", "precedent_letter"],
        "prong1_endeavor_description": ["style_guide", "firm_convention", "precedent_letter"],
        "prong1_substantial_merit": ["style_guide", "firm_convention", "precedent_letter"],
        "prong1_national_importance_welfare": ["style_guide", "firm_convention", "precedent_letter"],
        "prong1_national_importance_initiative": ["style_guide", "firm_convention", "precedent_letter"],
        "prong2_educational_background": ["style_guide", "firm_convention", "precedent_letter"],
        "prong2_certifications_licensure": ["style_guide", "firm_convention", "precedent_letter"],
        "prong2_professional_experience": ["style_guide", "firm_convention", "precedent_letter"],
        "prong2_professional_memberships": ["style_guide", "firm_convention", "precedent_letter"],
        "prong2_lectures_presentations": ["style_guide", "firm_convention", "precedent_letter"],
        "prong2_peer_recognition": ["style_guide", "firm_convention", "precedent_letter"],
        "prong2_expert_opinion_base": ["style_guide", "precedent_letter"],
        "prong3_endeavor_flexibility": ["style_guide", "firm_convention", "precedent_letter"],
        "prong3_public_interest": ["style_guide", "firm_convention", "precedent_letter"],
        "prong3_labor_market_shortage": ["style_guide", "firm_convention", "precedent_letter"],
        "prong3_no_adverse_effect": ["style_guide", "firm_convention", "precedent_letter"],
        "prong3_economic_benefit": ["style_guide", "firm_convention", "precedent_letter"],
        "petition_conclusion": ["style_guide", "firm_convention", "precedent_letter"],
    }
    allowed_types = allowed_types_by_section.get(section_code)
    if not allowed_types:
        return (None, [])

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return (None, [])
        client = openai.OpenAI(api_key=api_key)
        response = client.embeddings.create(
            input=evidence_summary,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        query_vector = response.data[0].embedding
    except Exception:
        logger.exception(
            "KB style guidance embedding failed for section %s", section_code
        )
        return (None, [])

    try:
        rows = db.execute(
            text(
                """
                SELECT kc.id, kc.text, kc.chunk_index
                FROM kb_chunks kc
                JOIN kb_embeddings ke ON ke.kb_chunk_id = kc.id
                WHERE kc.firm_id = :firm_id
                  AND kc.kb_document_id IN (
                      SELECT id FROM kb_documents
                      WHERE firm_id = :firm_id
                        AND document_type = ANY(:allowed_types)
                        AND lifecycle_state = 'indexed'
                  )
                  AND ke.firm_id = :firm_id
                ORDER BY ke.embedding <=> CAST(:query_vec AS vector)
                LIMIT 3
                """
            ),
            {
                "firm_id": firm_id,
                "allowed_types": allowed_types,
                "query_vec": str(query_vector),
            },
        ).fetchall()
    except Exception:
        logger.exception(
            "KB style guidance retrieval failed for section %s", section_code
        )
        return (None, [])

    if not rows:
        return (None, [])

    chunk_ids = [row[0] for row in rows]
    guidance = "\n\n".join(
        f"Style guidance ({row[2]}): {row[1]}" for row in rows
    )
    return (guidance, chunk_ids)
