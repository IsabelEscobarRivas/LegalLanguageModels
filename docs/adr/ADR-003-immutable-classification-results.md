# ADR-003: Immutable Classification Results

**Status:** Accepted
**Date:** 2026-05-25

## Context

The platform will produce AI-generated classifications mapping document chunks to USCIS legal criteria and section affinity targets. These classifications will inform legal drafting. A choice was required: should classification results be mutable (updatable when the model improves or a human disagrees) or immutable (append-only, with human feedback stored separately)?

The pressure comes from legal auditability. If a classification result can be overwritten, the system cannot answer: "What did the AI believe about this document at the time the draft was generated?" That question is legally relevant if a petition is challenged.

## Decision

Classification results are immutable once written. A `classification_results` row is never updated or deleted. When a human reviewer disagrees with a classification, their feedback is written to a separate `classification_feedback` table that references the original result. When a model is retrained and re-classifies a document, a new `classification_results` row is created — the old row is retained.

## Alternatives Considered

**Mutable classification with version field.** Update the classification row but increment a version number. Rejected because: version fields on mutable rows do not prevent silent overwrites and create ambiguity about which version was active at draft generation time. Append-only is unambiguous.

**Delete and reinsert on reclassification.** Remove old classification, insert new one. Rejected because: deletion destroys the audit trail. A legal platform must be able to show the full history of how a document was classified over time.

**Store only the latest classification.** Keep one classification per chunk per criterion, always current. Rejected because: this makes it impossible to audit model drift or trace why a draft used a particular evidence assignment.

## Trade-Offs

**Gained:** Complete classification history for every chunk. Full auditability of model behavior over time. Human feedback and AI output are cleanly separated — no conflation of machine judgment and human judgment.

**Accepted:** The `classification_results` table grows without bound as models are retrained. Queries for "current" classification must filter to the latest result per chunk per criterion. This adds query complexity that a mutable design would not require.

## Consequences

Every service that consumes classification results must explicitly query for the latest result per chunk — there is no single "current" row. Generation services in Sprint 4 must join `classification_results` on `(chunk_id, criteria_id)` ordered by `classified_at DESC` and take the first row. QA must verify that no code path issues `UPDATE` or `DELETE` against `classification_results`.

## Invariants Introduced

- `classification_results` rows are never updated or deleted
- Human feedback is stored in `classification_feedback`, never written back to `classification_results`
- Re-classification creates new rows; old rows are retained
- Generation always uses the latest classification at time of draft creation, recorded in the generation trace

## Related Components

`classification_results` (Sprint 3), `classification_feedback` (Sprint 3), `generation_traces` (Sprint 4), `app/retrieval/router.py` (provenance chain that classification extends)
