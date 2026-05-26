# Architecture Decision Records

This directory contains the authoritative architectural decision records for LegalLanguageModels V2.

ADRs record major architectural decisions, the rationale behind them, rejected alternatives, accepted trade-offs, and long-term consequences. They are not implementation tickets, sprint summaries, or tutorials.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](ADR-001-retrieval-before-classification.md) | Retrieval Before Classification | Accepted | 2026-05-25 |
| [ADR-002](ADR-002-relational-db-operational-source-of-truth.md) | Relational Database as Operational Source of Truth | Accepted | 2026-05-25 |
| [ADR-003](ADR-003-immutable-classification-results.md) | Immutable Classification Results | Accepted | 2026-05-25 |
| [ADR-004](ADR-004-provenance-first-legal-ai-architecture.md) | Provenance-First Legal AI Architecture | Accepted | 2026-05-25 |
| [ADR-005](ADR-005-classification-as-evidence-routing.md) | Classification as Evidence Routing for Narrative Generation | Accepted | 2026-05-25 |
| [ADR-006](ADR-006-paragraph-chunking-citation-extraction-visa-routing.md) | Paragraph-Level Chunking, Citation Extraction, and Visa-Type-Aware Section Affinity Routing | Accepted | 2026-05-26 |
| [ADR-007](ADR-007-knowledge-base-parallel-rag-pipeline.md) | Knowledge Base as a Parallel RAG Pipeline for Rhetorical and Structural Style Guidance | Accepted | 2026-05-26 |
| [ADR-008](ADR-008-taxonomy-aware-kb-retrieval.md) | Taxonomy-Aware Knowledge Base Retrieval | Accepted | 2026-05-26 |

## Conventions

- ADR numbers are permanent and sequential. A superseded ADR retains its number; its status changes to `Superseded` with a reference to the superseding ADR.
- New ADRs are always `Proposed` first. The architect moves them to `Accepted` after team review.
- No ADR content is ever deleted. Deprecated decisions are marked `Deprecated` with rationale.

## Architectural Invariants

The following invariants are foundational across all ADRs. Any decision that violates an invariant requires an explicit superseding ADR:

- Document versioning is append-only
- AI outputs are immutable
- Human feedback does not mutate AI outputs
- Provenance is mandatory on all AI-generated content
- Retrieval must preserve full traceability to source chunk and document version
- `case_id` is the tenant boundary
- JWT boundaries are enforced server-side
- PostgreSQL is the single operational source of truth
- Alembic is the only permitted schema migration mechanism
- Classification and generation are evidence-grounded
