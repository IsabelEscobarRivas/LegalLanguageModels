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
) -> Optional[str]:
    """Retrieve firm-scoped KB style guidance for a draft section.

    When db or firm_id is omitted, returns None so existing callers remain
    unchanged until Phase 4 wires generation context.
    """
    if db is None or firm_id is None:
        return None

    allowed_types_by_section = {
        "background": ["style_guide", "firm_convention"],
        "experience": ["style_guide", "firm_convention"],
        "achievements": ["style_guide", "firm_convention"],
        "expert_opinion": ["style_guide"],
        "impact": ["style_guide", "firm_convention", "precedent_letter"],
        "conclusion": ["style_guide", "firm_convention", "precedent_letter"],
    }
    allowed_types = allowed_types_by_section.get(section_code)
    if not allowed_types:
        return None

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
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
        return None

    try:
        rows = db.execute(
            text(
                """
                SELECT kc.text, kc.chunk_index
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
        return None

    if not rows:
        return None

    return "\n\n".join(
        f"Style guidance ({row[1]}): {row[0]}" for row in rows
    )
