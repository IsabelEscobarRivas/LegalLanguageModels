# ADR-007: Knowledge Base as a Parallel RAG Pipeline for Rhetorical and Structural Style Guidance

**Status:** Accepted
**Date:** 2026-05-26
**Supersedes:** N/A
**Superseded by:** N/A

## Context

Sprints 1-4 establish an evidence pipeline: uploaded documents are chunked, embedded, classified against USCIS criteria, and used to generate legal draft sections. The evidence pipeline answers the question "what facts support this applicant's petition?"

However, generation quality depends on more than evidence. It depends on the LLM understanding what rhetorical and structural patterns characterize strong legal argumentation for each visa type and section — the argument structure, citation conventions, and persuasive framing that attorneys use when arguing each criterion. This is not something the evidence pipeline can supply, because the applicant's own documents are evidence, not examples of legal reasoning style.

Review of real petition letters (Daniel Maceratesi Enjiu EB-1, Felipe Cusnir EB-2 NIW) confirmed that approved petition letters follow highly structured rhetorical patterns specific to each visa type and criterion; that the quality gap between generic legal writing and criterion-specific immigration writing is significant; and that attorneys and paralegals accumulate institutional knowledge — winning letters, preferred argument structures, firm style — that currently lives in email attachments and filing cabinets, not in any queryable system.

A knowledge base layer addresses this gap by making institutional legal writing knowledge queryable and injectable into the generation pipeline as rhetorical and structural style guidance.

## Provenance Categories

This ADR formalizes three distinct provenance categories. These categories must remain architecturally separated at every layer of the system:

**Evidence provenance** — supports factual and legal claims about the applicant. Evidence provenance participates in generation_traces. Every generated sentence that asserts a fact about the applicant must trace to an evidence provenance chain: document → document_version → chunk → classification_result → citation_text. This is the legally authoritative chain.

**KB provenance** — supports rhetorical and structural conditioning only. KB provenance never participates in evidentiary provenance. KB content informs how the LLM structures and frames an argument — it does not supply facts about the applicant. KB provenance is advisory context, not legal authority.

**Template/prompt provenance** — influences generation structure and orchestration. The prompt_templates table records which template was used for each section, stored in draft_sections.prompt_template_id. Template provenance is distinct from both evidence and KB provenance — it records the instructions given to the model, not the content the model drew on.

These three categories must never be conflated. A generation_trace row represents evidence provenance only. KB influence and template influence are recorded separately in draft_sections and are explicitly excluded from the evidentiary chain.

## Decision

A knowledge base pipeline is introduced as a parallel RAG system alongside the evidence pipeline. The two pipelines are architecturally separated and serve different purposes:

The evidence pipeline answers: "what facts does this applicant have?"
The knowledge base pipeline answers: "what rhetorical and structural patterns characterize strong legal argumentation for this section?"

Knowledge base documents are uploaded separately from case evidence. They are chunked and embedded using the same infrastructure but stored in separate tables (kb_documents, kb_chunks, kb_embeddings) and a separate S3 prefix (knowledge-base/). They are never classified against USCIS criteria. They never appear in the provenance chain of a generated draft. They are retrieved at generation time as advisory context for stylistic and rhetorical guidance — not as authoritative legal reasoning — and injected into the prompt as examples.

The knowledge base is scoped at the firm level — not the case level. A firm's approved letters, style guides, and example sections are available to all cases within that firm. JWT claims are extended to carry a firm_id claim alongside case_ids. Knowledge base access is gated by firm_id. Cross-firm KB retrieval is prohibited under all circumstances.

## KB Influence Boundaries

KB retrieval may influence:

- Rhetorical framing of legal arguments
- Argument structure within a section
- Section organization and paragraph sequencing
- Stylistic conventions such as citation format and formality level

KB retrieval may never:

- Introduce factual claims about the applicant not present in the evidence pipeline
- Become evidentiary support for any USCIS criterion
- Substitute for applicant evidence in any section
- Appear in generation_traces as a source of generated content

Evidentiary primacy is absolute. KB guidance conditions how the LLM writes — it does not determine what the LLM asserts.

## Alternatives Considered

**Few-shot examples in prompt templates only.** Store 1-2 example paragraphs directly in the prompt_templates.examples field. Simpler — no new infrastructure. Rejected as the sole solution because: static examples in prompt templates cannot be searched or updated without a new template version. A firm with 50 approved letters cannot fit them in a prompt field. Retrieval-based examples are more flexible and more powerful. The examples field added in S4-A02 remains — it serves as a static fallback when no KB document matches at runtime. These two mechanisms are complementary but distinct: prompt_templates.examples is versioned static guidance; KB retrieval is dynamic runtime-conditioned style guidance retrieved based on the specific applicant profile and section being generated.

**Single unified pipeline.** Use the same chunks and embeddings tables for both evidence and knowledge base content, distinguished by a document_type field. Rejected because: mixing evidence and KB content in the same tables creates provenance contamination risk. A generation_trace that accidentally references a KB chunk instead of an evidence chunk would assert a fictional source as applicant evidence — a critical legal defect. Separate tables with separate schemas make this confusion structurally impossible.

**Vector database for knowledge base.** Use Pinecone or similar for KB embeddings since they don't need relational provenance. Rejected per ADR-002 — PostgreSQL is the single operational source of truth. pgvector handles KB retrieval at the volumes expected for a legal platform.

## Trade-Offs

**Gained:** Generation quality improves as the firm's institutional knowledge accumulates in the KB. Attorneys can upload approved letters and immediately improve all future drafts. KB content is searchable and retrievable — it scales with the firm's practice. Style guidance is dynamic — different approved letters can be retrieved for different applicant profiles. The three-category provenance model makes the system auditable at every layer.

**Accepted:** New infrastructure — three new tables, new S3 prefix, new upload endpoint, new retrieval service. JWT claims must be extended to carry firm_id. The separation between KB content and evidence content must be enforced in every code path — a lapse would be a legal liability. KB documents require curation — a poorly written example letter in the KB degrades generation quality across all cases that firm owns.

**Critical failure mode:** A generated statement derived from KB guidance that is represented as applicant evidence constitutes provenance contamination and invalidates the evidentiary chain. This failure mode is architecturally prevented by the separation of tables and the exclusion of KB references from generation_traces. Any code path that allows a KB chunk ID to appear in a generation_trace row is a critical defect requiring immediate remediation.

## Consequences

Sprint 5 must implement:

- kb_documents, kb_chunks, kb_embeddings tables — migration required
- knowledge-base/ S3 prefix handling in app/ingestion/s3.py
- KB upload endpoint: POST /knowledge-base/documents
- KB search endpoint: POST /knowledge-base/search
- KB retrieval integration in generation service — called per section before prompt assembly
- firm_id added to JWT claims and cases table
- KB access gated by firm_id via a new require_firm_access dependency
- QA must verify that no KB chunk ID ever appears in generation_traces

Generation service in Sprint 4 must be designed with a KB injection point — a function `get_kb_style_guidance(visa_type, section_code, evidence_summary) -> str | None`. In Sprint 4 this function returns None always. In Sprint 5 it returns KB-retrieved rhetorical guidance. This interface must be defined and stubbed in Sprint 4 even though the implementation is deferred. The stub must be called in the generation pipeline so Sprint 5 can implement it by replacing the stub body only — no caller changes required.

## Invariants Introduced

- KB content never appears in generation_traces — it is advisory rhetorical context, not evidentiary provenance
- KB documents are never classified against USCIS criteria
- KB retrieval is firm-scoped — never case-scoped
- Cross-firm KB retrieval is prohibited under all circumstances
- Evidence pipeline and KB pipeline share infrastructure (pgvector, S3, chunking) but never share tables
- Generation service always calls the KB injection point — Sprint 4 returns None, Sprint 5 returns rhetorical guidance
- A generated sentence citing KB content as applicant evidence is a critical defect
- prompt_templates.examples is static versioned fallback — KB retrieval is dynamic runtime-conditioned guidance — these are complementary, not interchangeable
- Provenance contamination — KB content represented as applicant evidence — invalidates the evidentiary chain and is an unrecoverable defect

## Related Components

`kb_documents`, `kb_chunks`, `kb_embeddings` (Sprint 5 — pending), `knowledge-base/` S3 prefix (Sprint 5), `app/generation/service.py` (KB injection point stubbed in Sprint 4), `app/core/auth.py` (firm_id claim — Sprint 5), `cases` table (firm_id column — Sprint 5), `prompt_templates.examples` (static fallback when KB returns None)

## Summary of refinements added

- Provenance categories formalized — evidence, KB, and template provenance are now explicit architectural categories with distinct roles and participation rules
- KB influence boundaries made explicit — what KB may and may not influence is now a formal list, not implied
- Critical failure mode documented — provenance contamination is named, defined, and its prevention mechanism is stated
- prompt_templates.examples vs KB retrieval clarified — static versioned fallback vs dynamic runtime-conditioned guidance
- Multi-tenant isolation invariant made explicit — cross-firm KB retrieval prohibited under all circumstances
- KB framed as advisory context — "rhetorical and structural conditioning" replaces "excellent legal writing"
- Conceptual framing sharpened — KB answers "what rhetorical patterns characterize strong argumentation" not "what does good writing look like"

### New invariants introduced

- Cross-firm KB retrieval prohibited under all circumstances
- prompt_templates.examples and KB retrieval are complementary not interchangeable
- Provenance contamination invalidates the evidentiary chain and is an unrecoverable defect
