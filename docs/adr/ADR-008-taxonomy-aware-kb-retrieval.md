# ADR-008: Taxonomy-Aware Knowledge Base Retrieval

**Status:** Superseded
**Date:** 2026-05-26
**Supersedes:** N/A
**Superseded by:** [ADR-014](ADR-014-rag-2-template-driven-generation-architecture.md) (RAG 2 Template-Driven Generation Architecture)
**Extends:** ADR-007 (Knowledge Base as Parallel RAG Pipeline)

> **Note:** Generation-time KB retrieval on `kb_chunks` with `document_type` / section-key filtering is superseded by template-driven retrieval on `kb_templates` per ADR-014. This ADR remains authoritative for the historical rationale behind taxonomy-aware filtering.

## Context

ADR-007 established the knowledge base as a parallel RAG pipeline for rhetorical and structural style guidance, separated from the evidence pipeline by architecture and provenance boundaries. That ADR defined the KB as a source of "rhetorical and structural patterns characterizing strong legal argumentation."

Sprint 4 validation revealed a concrete limitation of pure semantic retrieval for KB guidance: when the system generates the background section for an EB-2 NIW petition, semantic similarity alone cannot reliably retrieve background-specific examples because the embedding space does not reliably encode section-level rhetorical function. A CV's education paragraphs and a professional plan's experience paragraphs may be semantically similar — both describe professional credentials — but they serve fundamentally different rhetorical roles in a petition letter.

This revealed a deeper architectural truth: the KB is not merely a repository of approved writing samples. It is an institutional legal reasoning memory that encodes:

- Rhetorical patterns specific to visa types
- Section semantics (what belongs in background vs experience)
- Criterion semantics (how C1 is argued vs C2)
- Document-type semantics (how a CV argues differently than an expert opinion letter)
- Firm-level precedent for how specific criteria have been successfully argued before

Semantic retrieval alone cannot capture these distinctions. A hybrid approach — symbolic filtering before semantic ranking — is required.

## Decision

KB retrieval is redesigned as a two-stage hybrid process: symbolic filtering on taxonomy metadata followed by semantic similarity ranking within the filtered candidate set. This mirrors how attorneys mentally retrieve precedent: first narrow by legal and rhetorical context, then compare similarity within that narrowed set.

**Stage 1 — Symbolic filtering (hard constraints):**

All of the following must match before a KB chunk is eligible for retrieval:

- firm_id — cross-firm KB retrieval remains prohibited per ADR-007
- visa_type — EB1, EB2, or BOTH
- section_code — the specific section being generated (nullable — null means applies to all sections)
- document_type — optional filter when generation context implies document-type-specific guidance

**Stage 2 — Semantic similarity ranking:**

Within the filtered candidate set, rank by cosine similarity to the evidence summary for the section being generated. Return top-k results.

This is significantly more robust than pure embedding similarity and prevents cross-section rhetorical contamination — expert opinion examples never pollute background generation, and policy report examples never pollute experience generation.

## Document Taxonomy

The KB schema is extended to capture taxonomy metadata on every KB document:

```sql
CREATE TABLE kb_documents (
  id              VARCHAR(36)   PRIMARY KEY,
  firm_id         VARCHAR(36)   NOT NULL,
  title           VARCHAR(200)  NOT NULL,
  visa_type       VARCHAR(20)   NOT NULL CHECK (visa_type IN ('EB1','EB2','BOTH')),
  document_type   VARCHAR(50)   NOT NULL,
  section_code    VARCHAR(50)   NULL,
  criteria_codes  JSONB         NULL,
  approved_by     VARCHAR(255)  NULL,
  approved_at     TIMESTAMP     NULL,
  s3_key          VARCHAR(1000) NOT NULL,
  created_at      TIMESTAMP     NOT NULL DEFAULT NOW()
);
```

`document_type` encodes rhetorical role semantics — not merely file format:

| document_type | Rhetorical role | Primary sections |
|---|---|---|
| resume | Chronological evidence of career progression | background, experience |
| support_letter | Peer validation of standing and impact | expert_opinion, achievements |
| expert_opinion_letter | Authority framing and criterion interpretation | expert_opinion |
| petition_letter | Full legal argument structure | all sections |
| policy_report | National importance framing | impact |
| membership_certificate | Recognition and standing evidence | achievements |
| academic_record | Educational credential evidence | background |
| professional_plan | Endeavor definition and positioning | experience, impact |

`document_type` is more than metadata — it encodes the rhetorical role of the document in a legal petition. Future retrieval behavior should become increasingly document-type-aware as the KB accumulates examples across document types.

## Attorney KB Curation Workflow

The KB is not populated automatically from uploaded case documents. It is curated explicitly by attorneys:

1. Attorney uploads an approved petition letter or supporting document to the KB
2. Attorney tags: visa_type, document_type, section_code (if section-specific), criteria_codes
3. Attorney marks as approved_by with their identity — this is the human quality gate
4. System chunks at the section level using paragraph chunking, embeds, stores with taxonomy
5. KB chunks inherit parent document taxonomy metadata

The `approved_by` field is mandatory for KB documents — unapproved content is never retrieved.

## KB as Institutional Legal Reasoning Memory

The KB encodes five categories of institutional knowledge:

**Rhetorical patterns** — how strong attorneys frame arguments for each criterion and section.

**Section semantics** — what content belongs in each section and how it is structured.

**Criterion semantics** — how C1 is argued differently than C2; how EB1_H differs from EB1_D.

**Document-type semantics** — how a CV contributes differently than an expert opinion letter; how a policy report is cited differently than a support letter.

**Firm-level precedent** — which arguments have worked before for this firm's cases, which sections have been strongest, which document types have been most persuasive.

As the KB accumulates approved content, generation quality improves automatically — not because the LLM changes but because its rhetorical priors become more precise.

## Relationship to Routing

The KB does not fix upstream classification routing. Classification routing integrity remains the responsibility of `criteria_section_affinity_defaults` and the classifier prompt. The KB makes generation more robust to routing imperfection by providing section-conditioned rhetorical priors — but it does not substitute for correct routing.

This distinction is explicit and must remain so. If a CV's education paragraphs route to experience instead of background due to a routing gap, the KB can help the experience section be written with appropriate framing — but it cannot move the evidence to background. Routing integrity still matters.

## Alternatives Considered

**Pure semantic retrieval.** Search all KB chunks by embedding similarity without symbolic pre-filtering. Rejected because: semantic similarity does not reliably encode section-level rhetorical function. Expert opinion examples and background examples may be semantically similar but rhetorically incompatible. Cross-section contamination degrades generation quality.

**Document-level retrieval only.** Retrieve whole approved letters rather than chunks. Rejected because: a full petition letter contains content for all six sections. Retrieving it for a single section retrieval query provides too much irrelevant context and dilutes the rhetorical signal.

**Automatic KB population from case documents.** Populate the KB automatically from successfully generated drafts. Rejected because: automatically populated KB content bypasses the attorney quality gate. Only attorney-approved content belongs in the KB. Automatic population risks propagating errors.

## Trade-Offs

**Gained:** Section-conditioned retrieval prevents cross-section rhetorical contamination. Document-type-aware retrieval provides appropriate stylistic priors for each document type. Symbolic pre-filtering reduces the semantic search space, improving both speed and precision. Attorney-curated KB ensures quality control on all style guidance.

**Accepted:** KB curation requires attorney time — the KB starts empty and improves only as attorneys explicitly curate it. Taxonomy metadata must be accurate — incorrectly tagged KB documents degrade retrieval precision. The `approved_by` requirement means the KB cannot be auto-populated from generated drafts.

## Consequences

Sprint 5 must implement the full KB pipeline per ADR-007, with the extended schema defined here. The `get_kb_style_guidance` stub in Sprint 4's generation service must be replaced with the two-stage hybrid retrieval implementation. The KB upload endpoint must enforce taxonomy metadata collection and the `approved_by` requirement before a document is marked retrieval-eligible.

The `kb_chunks` table must store taxonomy metadata inherited from `kb_documents` so retrieval can filter at the chunk level without joining back to the parent document on every query.

## Invariants Introduced

- KB taxonomy metadata influences retrieval eligibility and stylistic conditioning — not evidentiary truth
- Taxonomy tags are routing aids, retrieval constraints, and rhetorical metadata — never legal facts or evidentiary support
- Symbolic filtering always precedes semantic ranking — semantic-only KB retrieval is prohibited
- Cross-firm KB retrieval is prohibited under all circumstances (per ADR-007, reinforced here)
- Only attorney-approved KB documents are retrieval-eligible — `approved_by` is mandatory
- `document_type` encodes rhetorical role semantics — it is not merely a file format label
- The KB makes generation robust to routing imperfection — it does not substitute for routing integrity

## Related Components

`kb_documents`, `kb_chunks`, `kb_embeddings` (Sprint 5), `get_kb_style_guidance` stub in `app/generation/templates.py` (to be replaced in Sprint 5), `criteria_section_affinity_defaults` (routing — separate concern), `app/core/auth.py` (firm_id claim — Sprint 5), ADR-007 (parent architecture), ADR-009 (multi-tenant firm isolation — pending)
