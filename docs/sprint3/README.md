# Sprint 3 — Classification + Evidence Routing Foundation

## Objective

Establish the legal intelligence layer: dual-axis classification (USCIS criteria + section affinity), immutable classification results, human feedback workflow, and coverage gap detection.

## Architecture Specs

- [S3-A01 — Classification Architecture](../adr/S3-A01-classification-architecture-spec.md)
- [S3-A02 — Legal Criteria Taxonomy](../adr/S3-A02-criteria-taxonomy-spec.md)
- [S3-A03 — Section Affinity](../adr/S3-A03-section-affinity-spec.md)

## Implementation Tickets

| Ticket | Title | Status |
|--------|-------|--------|
| S3-D01 | Minimum Similarity Threshold on Retrieval | Pending |
| S3-D02 | Protect Sprint 1 Endpoints with JWT | Pending |
| S3-D03 | Criteria Reference Table | Pending |
| S3-D04 | Immutable Classification Results | Pending |
| S3-D05 | Classification Service | Pending |
| S3-D06 | Classification Feedback Workflow | Pending |
| S3-D07 | Coverage Gap Detection | Pending |
| S3-D08 | Event Pagination | Pending |

## Key Invariants for Sprint 3

- classification_results is append-only — no UPDATE or DELETE ever
- classification_feedback never mutates classification_results
- Every classification row carries full provenance: chunk_id, document_version_id, case_id
- Coverage gap detection runs before generation — never skipped
- conclusion section is generated, not retrieved
