import logging
import os
import re
import uuid
from typing import Optional

import openai
from sqlalchemy.orm import Session

from app.core.models import (
    Chunk,
    ClassificationResult,
    CriteriaReference,
    Document,
    DocumentVersion,
    DraftOutput,
    DraftSection,
    KBGuidanceTrace,
    PromptTemplate,
    SectionAffinityReference,
)
from app.generation.coverage_gate import check_coverage_gate
from app.generation.templates import (
    get_active_template,
    get_kb_style_guidance,
    render_prompt,
)
from app.generation.traces import build_trace_dicts, write_generation_traces


logger = logging.getLogger(__name__)

GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "gpt-4o")
GENERATION_MODEL_VERSION = os.environ.get("GENERATION_MODEL_VERSION", "1.0")
EVIDENCE_TOP_K = int(os.environ.get("EVIDENCE_TOP_K", 5))

_LEGACY_SECTION_ORDER = [
    "background",
    "experience",
    "expert_opinion",
    "achievements",
    "impact",
    "conclusion",
]

# Backward compatibility for callers not yet migrated to _build_section_order.
SECTION_ORDER = _LEGACY_SECTION_ORDER


def _build_section_order(db: Session, visa_type: str, case_id: str) -> list[str]:
    """Build the ordered list of section codes for this draft.

    Order:
      1. Structural sections (no prong): introduction, statement_of_law,
         advanced_degree_qualification
      2. Prong 1 sections in display_order
      3. Prong 2 sections in display_order (excluding expert opinion base)
      4. Dynamic expert opinion sections — one per classified expert document
      5. Prong 3 sections in display_order
      6. Conclusion: petition_conclusion

    Falls back to old SECTION_ORDER if no new templates exist (backward compat).
    Never raises.
    """
    try:
        new_templates = (
            db.query(PromptTemplate)
            .filter(
                PromptTemplate.visa_type == visa_type,
                PromptTemplate.is_active.is_(True),
                PromptTemplate.section_code == "introduction",
            )
            .first()
        )

        if new_templates is None:
            return list(_LEGACY_SECTION_ORDER)

        structural = [
            "introduction",
            "statement_of_law",
            "advanced_degree_qualification",
        ]

        prong1 = [
            "prong1_endeavor_description",
            "prong1_substantial_merit",
            "prong1_national_importance_welfare",
            "prong1_national_importance_initiative",
        ]

        prong2_static = [
            "prong2_educational_background",
            "prong2_certifications_licensure",
            "prong2_lectures_presentations",
            "prong2_professional_experience",
            "prong2_professional_memberships",
            "prong2_peer_recognition",
        ]

        expert_sections = _discover_expert_sections(db, case_id, visa_type)

        prong3 = [
            "prong3_endeavor_flexibility",
            "prong3_public_interest",
            "prong3_labor_market_shortage",
            "prong3_no_adverse_effect",
            "prong3_economic_benefit",
        ]

        conclusion = ["petition_conclusion"]

        return (
            structural
            + prong1
            + prong2_static
            + expert_sections
            + prong3
            + conclusion
        )

    except Exception:
        logger.exception("_build_section_order failed — using fallback")
        return list(_LEGACY_SECTION_ORDER)


def _discover_expert_sections(
    db: Session, case_id: str, visa_type: str
) -> list[str]:
    """Find expert opinion documents classified for this case and return
    dynamic section codes in the format prong2_expert_opinion_{slug}.

    Looks for ClassificationResult rows where section_affinity code is
    'prong2_expert_opinion_base' or 'expert_opinion' (old code).
    Extracts expert name from source Document.original_name.
    Returns deduplicated list of dynamic section codes.
    Never raises.
    """
    try:
        results = (
            db.query(Document.original_name)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .join(Chunk, Chunk.document_version_id == DocumentVersion.id)
            .join(
                ClassificationResult,
                ClassificationResult.chunk_id == Chunk.id,
            )
            .join(
                SectionAffinityReference,
                SectionAffinityReference.id
                == ClassificationResult.section_affinity_id,
            )
            .filter(
                ClassificationResult.case_id == case_id,
                SectionAffinityReference.code.in_([
                    "prong2_expert_opinion_base",
                    "expert_opinion",
                ]),
                Document.retrieval_eligible.is_(True),
                Document.generation_eligible.is_(True),
            )
            .distinct()
            .all()
        )

        seen = set()
        sections = []
        prefix = "prong2_expert_opinion_"
        for (original_name,) in results:
            name = re.sub(r"\.[^.]+$", "", original_name)
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            slug = slug[:27]  # cap slug: prefix is 22 chars, total must be under 50
            code = f"{prefix}{slug}"
            if code not in seen:
                seen.add(code)
                sections.append(code)

        return sections

    except Exception:
        logger.exception("_discover_expert_sections failed")
        return []


def _resolve_evidence_section_codes(section_code: str) -> list[str]:
    """Map a section code to the evidence section affinity codes to query.

    Dynamic expert opinion sections query both the new base code and
    the old code for backward compatibility.
    Static new codes query only themselves.
    Old codes query only themselves.
    """
    if section_code.startswith("prong2_expert_opinion_"):
        return ["prong2_expert_opinion_base", "expert_opinion"]
    return [section_code]


def generate_draft(
    db: Session,
    case_id: str,
    document_id: str,
    version_id: str,
    visa_type: str,
    force_generate: bool = False,
) -> dict:
    """Generate a section-based legal draft for a case.

    Returns a result dict with keys:
        status: 'ok' | 'coverage_blocked' | 'not_found' | 'failed'
        draft_id: str (when status='ok')
        overall_status: str
        coverage_summary: dict
        missing_criteria: list
        sections: list[dict]
        override_available: bool (when status='coverage_blocked')

    Never raises.
    """
    try:
        document = (
            db.query(Document)
            .filter(Document.id == document_id, Document.case_id == case_id)
            .first()
        )
        if document is None:
            return {"status": "not_found"}

        firm_id = document.case.firm_id if document.case else None
        if firm_id is None:
            return {"status": "failed", "reason": "firm_id_not_resolved"}

        gate = check_coverage_gate(db, case_id, visa_type, force_generate)
        if not gate["allowed"]:
            return {
                "status": "coverage_blocked",
                "overall_status": gate["overall_status"],
                "missing_criteria": gate["missing_criteria"],
                "insufficient_criteria": gate["insufficient_criteria"],
                "override_available": gate["override_available"],
            }

        draft = DraftOutput(
            case_id=case_id,
            visa_type=visa_type,
            document_version_id=version_id,
            overall_status=gate["overall_status"],
            coverage_summary={
                "overall_status": gate["overall_status"],
                "missing_criteria": gate["missing_criteria"],
                "insufficient_criteria": gate["insufficient_criteria"],
                "coverage_detail": gate["coverage_detail"],
            },
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        sections_so_far: list[dict] = []
        section_order = _build_section_order(db, visa_type, case_id)
        for section_code in section_order:
            section_result = _generate_section(
                db=db,
                draft_output_id=draft.id,
                case_id=case_id,
                version_id=version_id,
                visa_type=visa_type,
                section_code=section_code,
                firm_id=firm_id,
                coverage_summary=draft.coverage_summary,
                prior_sections=sections_so_far,
            )
            if section_result is None:
                logger.warning(
                    "Section generation failed for draft_id=%s section_code=%s",
                    draft.id,
                    section_code,
                )
                continue
            sections_so_far.append(section_result)

        return {
            "status": "ok",
            "draft_id": draft.id,
            "overall_status": draft.overall_status,
            "coverage_summary": draft.coverage_summary,
            "missing_criteria": gate["missing_criteria"],
            "sections": sections_so_far,
        }

    except Exception as exc:
        logger.exception("Draft generation failed for case_id=%s", case_id)
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after draft generation failure also failed")
        return {"status": "failed", "reason": str(exc)}


def _generate_section(
    db: Session,
    draft_output_id: str,
    case_id: str,
    version_id: str,
    visa_type: str,
    section_code: str,
    firm_id: str,
    coverage_summary: dict,
    prior_sections: list[dict],
) -> Optional[dict]:
    """Generate one section. Returns section dict or None on failure."""
    try:
        template = get_active_template(db, visa_type, section_code)
        if template is None and section_code.startswith("prong2_expert_opinion_"):
            template = get_active_template(db, visa_type, "prong2_expert_opinion_base")
        if template is None:
            logger.error(
                "No active template for visa_type=%s section_code=%s",
                visa_type,
                section_code,
            )
            return None

        if section_code in ("conclusion", "petition_conclusion"):
            evidence_results: list[dict] = []
        else:
            evidence_results = _fetch_section_evidence(
                db, case_id, section_code, visa_type
            )

        if (
            section_code not in ("conclusion", "petition_conclusion")
            and not evidence_results
        ):
            logger.warning(
                "No evidence for section %s in case %s — returning sentinel",
                section_code,
                case_id,
            )
            section_row = DraftSection(
                draft_output_id=draft_output_id,
                section_code=section_code,
                content=(
                    "INSUFFICIENT EVIDENCE: No classified evidence is available "
                    "for this section. Additional documents are required."
                ),
                prompt_template_id=template.id,
                model_name=template.model_name,
                model_version=GENERATION_MODEL_VERSION,
                tokens_used=0,
            )
            db.add(section_row)
            db.commit()
            db.refresh(section_row)
            return {
                "section_code": section_code,
                "content": (
                    "INSUFFICIENT EVIDENCE: No classified evidence is available "
                    "for this section. Additional documents are required."
                ),
                "citations_used": 0,
                "tokens_used": 0,
                "traces": [],
            }

        evidence_summary = " ".join(
            ev.get("citation_text", "") or ""
            for ev in evidence_results
        )
        kb_guidance, kb_chunk_ids = get_kb_style_guidance(
            visa_type,
            section_code,
            evidence_summary,
            db=db,
            firm_id=firm_id,
        )

        evidence_items = _format_evidence_items(evidence_results)
        variables = {
            "visa_type": visa_type,
            "section_name": section_code.replace("_", " ").title(),
            "applicant_name": "the applicant",
            "evidence_items": evidence_items,
            "coverage_summary": str(coverage_summary),
            "section_summaries": _format_prior_sections(prior_sections),
        }
        if section_code.startswith("prong2_expert_opinion_"):
            expert_name = "the expert"
            if evidence_results:
                src = evidence_results[0].get("source_document", "")
                name = re.sub(r"\.[^.]+$", "", src)
                name = re.sub(r"[-_]+", " ", name).strip()
                expert_name = name if name else "the expert"
            variables["expert_name"] = expert_name
        if kb_guidance:
            variables["kb_examples"] = kb_guidance

        system_prompt, user_prompt = render_prompt(template, variables)

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=template.model_name,
            temperature=template.temperature,
            max_tokens=template.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else None

        section_row = DraftSection(
            draft_output_id=draft_output_id,
            section_code=section_code,
            content=content,
            prompt_template_id=template.id,
            model_name=template.model_name,
            model_version=GENERATION_MODEL_VERSION,
            tokens_used=tokens_used,
            kb_guidance_applied=kb_guidance is not None,
        )
        db.add(section_row)
        db.commit()
        db.refresh(section_row)

        write_generation_traces(
            db=db,
            draft_section_id=section_row.id,
            classification_results=evidence_results,
        )

        if kb_guidance is not None and kb_chunk_ids:
            kb_trace_rows = [
                KBGuidanceTrace(
                    draft_section_id=section_row.id,
                    kb_chunk_id=chunk_id,
                    firm_id=firm_id,
                    guidance_type="style",
                )
                for chunk_id in kb_chunk_ids
            ]
            db.bulk_save_objects(kb_trace_rows)
            db.commit()

        return {
            "section_code": section_code,
            "content": content,
            "citations_used": len(evidence_results),
            "tokens_used": tokens_used,
            "traces": build_trace_dicts(evidence_results),
        }

    except Exception:
        logger.exception(
            "Section generation failed for draft_output_id=%s section_code=%s",
            draft_output_id,
            section_code,
        )
        return None


def _fetch_section_evidence(
    db: Session,
    case_id: str,
    section_code: str,
    visa_type: str,
) -> list[dict]:
    """Fetch top classification results for a section ordered by confidence.

    Returns list of dicts with keys:
        classification_result_id, chunk_id, citation_text,
        criteria_code, criteria_label, confidence_score,
        source_document, similarity_score
    """
    results = (
        db.query(
            ClassificationResult,
            CriteriaReference,
            Chunk,
            Document,
        )
        .join(
            CriteriaReference,
            CriteriaReference.id == ClassificationResult.criteria_id,
        )
        .join(
            SectionAffinityReference,
            SectionAffinityReference.id
            == ClassificationResult.section_affinity_id,
        )
        .join(Chunk, Chunk.id == ClassificationResult.chunk_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .join(Document, Document.id == DocumentVersion.document_id)
        .filter(
            ClassificationResult.case_id == case_id,
            SectionAffinityReference.code.in_(
                _resolve_evidence_section_codes(section_code)
            ),
            Document.retrieval_eligible.is_(True),
            Document.generation_eligible.is_(True),
        )
        .order_by(ClassificationResult.confidence_score.desc())
        .limit(EVIDENCE_TOP_K)
        .all()
    )

    return [
        {
            "classification_result_id": cr.id,
            "chunk_id": chunk.id,
            "citation_text": cr.citation_text,
            "criteria_code": criteria.code,
            "criteria_label": criteria.label,
            "confidence_score": cr.confidence_score,
            "source_document": doc.original_name,
            "similarity_score": None,
        }
        for cr, criteria, chunk, doc in results
    ]


def _format_evidence_items(evidence_results: list[dict]) -> list[str]:
    """Format evidence for prompt injection as numbered list strings."""
    seen_citations = set()
    deduped = []

    for ev in evidence_results:
        citation = ev.get("citation_text")
        if not citation or citation.strip() == "See source document":
            continue
        if citation not in seen_citations:
            seen_citations.add(citation)
            deduped.append(ev)

    if not deduped:
        seen_docs = set()
        for ev in evidence_results:
            doc = ev.get("source_document", "unknown")
            if doc not in seen_docs:
                seen_docs.add(doc)
                deduped.append(ev)

    items = []
    for i, ev in enumerate(deduped):
        citation = ev.get("citation_text") or "See source document"
        source = ev.get("source_document", "unknown")
        confidence = ev.get("confidence_score", 0.0)
        items.append(
            f'{i + 1}. "{citation}" ({source}, confidence: {confidence:.2f})'
        )
    return items


def _format_prior_sections(prior_sections: list[dict]) -> str:
    """Format prior section summaries for conclusion prompt."""
    if not prior_sections:
        return "No prior sections generated."
    parts = []
    for s in prior_sections:
        code = s.get("section_code", "unknown").replace("_", " ").title()
        content = s.get("content", "")
        preview = content[:300] + "..." if len(content) > 300 else content
        parts.append(f"{code}:\n{preview}")
    return "\n\n".join(parts)
