import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from app.core.models import PromptTemplate


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
) -> Optional[str]:
    """KB injection point — stub for Sprint 4.

    Sprint 5 replaces this body with KB retrieval logic.
    Callers must not be changed when Sprint 5 implements this.

    Returns None always in Sprint 4.
    """
    return None
