# ADR-004: Provenance-First Legal AI Architecture

**Status:** Accepted
**Date:** 2026-05-25

## Context

The platform generates AI-assisted legal drafts for immigration petitions. These drafts are submitted to USCIS and may be subject to audit, challenge, or request for evidence. A choice was required about the fundamental design philosophy: optimize for output quality (generate the best possible draft) or optimize for traceability (ensure every claim in a draft can be traced to a source document).

The pressure is domain-specific. In legal contexts, an unattributed claim is an unverifiable claim. A draft sentence asserting that an applicant "has been recognized internationally" must be traceable to the specific document, version, chunk, and classification result that grounded it. Without this, the system is a liability rather than an asset.

## Decision

Every AI output — classification result, retrieved chunk, generated draft sentence — carries mandatory provenance to its source. No AI output is surfaced to any consumer without the full provenance chain: document → document_version → chunk → embedding → retrieval_log → classification_result → generation_trace. Provenance is not optional metadata; it is a required field on every output schema.

## Alternatives Considered

**Output-first architecture.** Generate the best draft, then optionally attach sources. Common in consumer AI products. Rejected because: in legal drafting, a draft without traceable sources is unusable — attorneys cannot submit claims they cannot verify. Post-hoc attribution is less reliable than provenance built into the generation pipeline.

**Flat document references.** Attach document-level references to drafts (e.g. "based on Resume.pdf") without chunk-level granularity. Rejected because: document-level attribution does not tell the attorney which specific passage supports which claim. Chunk-level provenance is the minimum granularity for legal defensibility.

**Human-in-the-loop attribution.** Let the attorney manually tag which documents support which claims after draft generation. Rejected because: this defeats the efficiency goal of the platform and introduces human error into the attribution process that the system is capable of automating.

## Trade-Offs

**Gained:** Every draft is legally defensible at the chunk level. Attorneys can inspect the exact source passage for any generated claim. The system can be audited end-to-end. Model behavior is observable — if a draft uses a weak source, that is visible and correctable.

**Accepted:** Provenance requirements add schema complexity and query overhead. Every generation trace must store the list of chunks used, their versions, their classification results, and their similarity scores. This makes generation traces large and generation queries complex. Simpler architectures that generate first and attribute later are faster to build but unacceptable for this domain.

## Consequences

Generation in Sprint 4 cannot produce output without a complete provenance chain. The generation trace schema must store `chunk_ids[]`, `classification_result_ids[]`, `retrieval_log_id`, and `model_name`/`version` as required fields. QA must verify that no generated output reaches the API response layer without a corresponding `generation_trace` row. Future evaluation pipelines can use provenance chains to assess source quality automatically.

## Invariants Introduced

- No AI output is returned to any API consumer without a provenance chain
- Generation traces are required fields, not optional metadata
- Chunk-level attribution is the minimum granularity for all generated claims
- Provenance chains are immutable once written

## Related Components

`chunks`, `embeddings`, `retrieval_logs`, `classification_results` (Sprint 3), `generation_traces` (Sprint 4), `draft_outputs` (Sprint 4), all API response schemas in `app/core/schemas.py`
