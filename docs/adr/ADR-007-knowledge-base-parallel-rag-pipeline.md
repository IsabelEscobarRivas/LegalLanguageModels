# ADR-007: Knowledge Base as a Parallel RAG Pipeline for Style Guidance

**Status:** Accepted
**Date:** 2026-05-26
**Supersedes:** N/A
**Superseded by:** N/A

## Context

Sprints 1-4 establish an evidence pipeline: uploaded documents are chunked, embedded, classified against USCIS criteria, and used to generate legal draft sections. The evidence pipeline answers the question "what facts support this applicant's petition?"

However, generation quality depends on more than evidence. It depends on the LLM understanding what an excellent EB-1 or EB-2 NIW petition section looks like in practice — the legal argumentation style, the citation format, the rhetorical structure attorneys use to argue each criterion. This is not something the evidence pipeline can supply, because the applicant's own documents are evidence, not examples of good legal writing.

Review of real petition letters (Daniel Maceratesi Enjiu EB-1, Felipe Cusnir EB-2 NIW) revealed that:

Approved petition letters follow highly structured rhetorical patterns specific to each visa type and criterion
The quality gap between generic legal writing and criterion-specific immigration writing is significant
Attorneys and paralegals accumulate institutional knowledge — winning letters, preferred argument structures, firm style — that currently lives in email attachments and filing cabinets, not in any queryable system

A knowledge base layer addresses this gap by making institutional legal writing knowledge queryable and injectable into the generation pipeline as style guidance.

## Decision

A knowledge base pipeline is introduced as a parallel RAG system alongside the evidence pipeline. The two pipelines are architecturally separated and serve different purposes:

The evidence pipeline answers: "what facts does this applicant have?"
The knowledge base pipeline answers: "what does excellent legal writing for this section look like?"

Knowledge base documents are uploaded separately from case evidence. They are chunked and embedded using the same infrastructure but stored in separate tables (kb_documents, kb_chunks, kb_embeddings) and a separate S3 prefix (knowledge-base/). They are never classified against USCIS criteria. They never appear in the provenance chain of a generated draft. They are retrieved at generation time as style guidance only and injected into the prompt as examples.

The knowledge base is scoped at the firm level — not the case level. A firm's approved letters, style guides, and example sections are available to all cases within that firm. JWT claims are extended to carry a firm_id claim alongside case_ids. Knowledge base access is gated by firm_id.

## Alternatives Considered

**Few-shot examples in prompt templates only.** Store 1-2 example paragraphs directly in the prompt_templates.examples field. Simpler — no new infrastructure. Rejected as the sole solution because: static examples in prompt templates cannot be searched or updated without a new template version. A firm with 50 approved letters cannot fit them in a prompt field. Retrieval-based examples are more flexible and more powerful. The examples field added in S4-A02 remains — it serves as a fallback when no KB document matches.

**Single unified pipeline.** Use the same chunks and embeddings tables for both evidence and knowledge base content, distinguished by a document_type field. Rejected because: mixing evidence and KB content in the same tables creates provenance risk. A generation trace that accidentally references a KB chunk instead of an evidence chunk would be legally invalid — it would cite a fictional source rather than the applicant's actual documents. Separate tables with separate schemas make this confusion structurally impossible.

**Vector database for knowledge base.** Use Pinecone or similar for KB embeddings since they don't need relational provenance. Rejected per ADR-002 — PostgreSQL is the single operational source of truth. pgvector handles KB retrieval at the volumes expected for a legal platform.

## Trade-Offs

**Gained:** Generation quality improves as the firm's institutional knowledge accumulates in the KB. Attorneys can upload approved letters and immediately improve all future drafts. KB content is searchable and retrievable — it scales with the firm's practice. Style guidance is dynamic — different approved letters can be retrieved for different applicant profiles.

**Accepted:** New infrastructure — three new tables, new S3 prefix, new upload endpoint, new retrieval service. JWT claims must be extended to carry firm_id. The separation between KB content and evidence content must be enforced in every code path — a lapse would be a legal liability. KB documents require curation — garbage in, garbage out. A poorly written example letter in the KB degrades generation quality across all cases.

## Consequences

Sprint 5 must implement:

- kb_documents, kb_chunks, kb_embeddings tables — migration required
- knowledge-base/ S3 prefix handling in app/ingestion/s3.py
- KB upload endpoint: POST /knowledge-base/documents
- KB search endpoint: POST /knowledge-base/search
- KB retrieval integration in generation service — called per section before prompt assembly
- firm_id added to JWT claims and cases table
- KB access gated by firm_id in require_case_access or a new require_firm_access dependency

Generation service in Sprint 4 must be designed with a KB injection point — a function call that accepts (visa_type, section_code, evidence_summary) and returns example text or None. In Sprint 4 this function returns None always. In Sprint 5 it returns KB-retrieved content. This interface must be defined in Sprint 4 even though the implementation is deferred.

## Invariants Introduced

- KB content never appears in generation_traces — it is style guidance, not provenance
- KB documents are never classified against USCIS criteria
- KB retrieval is firm-scoped — never case-scoped
- Evidence pipeline and KB pipeline share infrastructure (pgvector, S3, chunking) but never share tables
- Generation service always calls the KB injection point — Sprint 4 returns None, Sprint 5 returns examples
- A generated sentence citing KB content as its source is a critical defect

## Related Components

`kb_documents`, `kb_chunks`, `kb_embeddings` (Sprint 5 — pending), `knowledge-base/` S3 prefix (Sprint 5), `app/generation/service.py` (KB injection point to be stubbed in Sprint 4), `app/core/auth.py` (firm_id claim — Sprint 5), `cases` table (firm_id column — Sprint 5), `prompt_templates.examples` (fallback when KB returns None)
