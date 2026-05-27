# ADR-010: Institutional Knowledge Base Operationalization and Provenance Separation

**Status:** Proposed
**Date:** 2026-05-26
**Authors:** Architect (Claude)
**Supersedes:** None
**Related:** ADR-004 (Provenance-first legal AI), ADR-007 (KB as parallel RAG pipeline), ADR-008 (Taxonomy-aware hybrid retrieval), ADR-009 (Multi-tenant firm isolation)

---

## Context

Sprint 5 established the KB schema, KB endpoints, firm-scoped retrieval, and the structural separation between `generation_traces` and `kb_guidance_traces`. The `ingest_kb_document` ARQ task exists but contains a stub body. KB documents can be uploaded but cannot progress past `lifecycle_state = 'uploaded'`. The `get_kb_style_guidance` function is implemented and firm-scoped but returns `(None, [])` because no KB documents reach `indexed` state.

Sprint 6 operationalizes the KB pipeline end-to-end. This requires defining the pipeline architecture, lifecycle state machine, failure semantics, retry semantics, observability contract, and the generation-time injection constraints that govern how institutional knowledge influences legal drafting without corrupting evidentiary provenance.

---

## Problem Statement

Three distinct problems must be solved in sequence:

**Problem 1 — Lifecycle operationalization.** KB documents exist in the database but cannot be made retrievable. The ingestion pipeline (extract → chunk → embed → index) does not exist. Without it, KB guidance is permanently inactive regardless of what documents are uploaded.

**Problem 2 — Observability gap.** `ProcessingEvent.case_id` is `NOT NULL`, which blocks KB pipeline events from being written. KB ingestion has no audit trail. Operators cannot observe pipeline progress or diagnose failures without direct database access.

**Problem 3 — Influence boundary enforcement.** When KB guidance does fire, the platform must structurally guarantee that guidance influences rhetoric only and never appears in `generation_traces` as pseudo-evidence. This guarantee must be mechanically enforced and QA-verifiable, not dependent on developer discipline.

---

## Architectural Decisions

### Decision 1: KB pipeline as a parallel ingestion architecture

The KB pipeline mirrors the case document pipeline structurally but operates on different source tables and target tables. It does not share code with the case document pipeline — it reuses the same patterns (paragraph chunking, OpenAI embedding, idempotent writes) but through a dedicated module (`app/kb/pipeline.py`).

**Rationale:** Sharing code between case and KB pipelines would create implicit coupling between the evidentiary pipeline and the institutional memory pipeline. This coupling would make it harder to evolve them independently and would create risk of evidentiary data accidentally flowing through KB paths (or vice versa). Structural parallelism preserves the separation that ADR-004 and ADR-007 require.

### Decision 2: Lifecycle state as the retrievability gate

A KB document is retrievable by generation if and only if `lifecycle_state = 'indexed'`. The `get_kb_style_guidance` SQL query already enforces this via `WHERE lifecycle_state = 'indexed'`. No code change is required to activate retrieval — operationalizing the pipeline is sufficient.

**Rationale:** Making retrievability a function of persisted state rather than runtime computation means the gate survives restarts, retries, and partial failures. A document that fails mid-pipeline stays in its last successfully completed state and is not retrievable until the full pipeline completes.

### Decision 3: Synchronous pipeline endpoint for Sprint 6A, async queue for Sprint 6B

`POST /kb/documents/{id}/ingest` runs the pipeline synchronously in Sprint 6A. Sprint 6B migrates it to enqueue the ARQ task and return `202 Accepted`.

**Rationale:** Synchronous execution in Sprint 6A allows QA validation without queue infrastructure complexity. The endpoint contract (inputs, outputs, lifecycle state transitions) is identical between 6A and 6B. Only the execution mechanism changes. This sequencing avoids debugging async pipeline failures before the pipeline itself is validated.

### Decision 4: Migration 0012 makes `processing_events.case_id` nullable

KB pipeline events are not case-scoped. Making `case_id` nullable on `processing_events` allows KB events to use the same event infrastructure without schema changes to the event table itself.

**Rationale:** Creating a separate `kb_processing_events` table would duplicate the event infrastructure for no architectural benefit. The `processing_events` table is already the platform's operational audit trail. Adding a nullable `case_id` and a `kb_document_id` field in the `detail` JSONB column is sufficient to distinguish KB events from case events.

### Decision 5: Provenance separation is structural, not conventional

`generation_traces` has FK constraints to `chunks` and `classification_results`. `kb_guidance_traces` has FK constraints to `kb_chunks` and `draft_sections`. There is no FK between these two tables and no shared column that could accidentally link them.

The structural verification query is:
```sql
SELECT COUNT(*) FROM generation_traces gt
JOIN kb_chunks kc ON kc.id = gt.chunk_id;
```
This must always return 0. It is a permanent platform invariant enforced by schema design and verified by QA on every Sprint 6B generation run.

**Rationale:** Conventional separation (developer discipline, code review) degrades over time as team membership changes and sprint pressure increases. Structural separation is enforced by the database at write time and is immune to human error.

### Decision 6: KB guidance injection is labeled and delimited in prompt assembly

When KB guidance fires, the assembled prompt contains two explicitly separated blocks:

```
[EVIDENCE BLOCK — citation_text values from classification_results]
[KB GUIDANCE BLOCK — style guidance from firm's indexed KB documents]
```

The system prompt includes an explicit instruction that KB guidance is advisory and must not be cited as evidence. This instruction is seeded via migration 0013 as an update to the relevant `prompt_templates` rows, not via runtime configuration.

**Rationale:** Prompt assembly is the last line of defense against KB guidance being treated as evidence by the LLM. The explicit delimitation and instruction reduce the probability of the model conflating institutional style guidance with case-specific evidence.

---

## State Machine Diagrams

```
KB Document Lifecycle:

    [UPLOADED]
        │
        │  chunk_kb_document()
        │  S3 fetch → paragraph split → KBChunk insert
        │
        ├─── success ──────────────────► [CHUNKED]
        │                                    │
        │                                    │  embed_kb_document()
        │                                    │  OpenAI embed → KBEmbedding insert
        │                                    │
        │                         ┌──── partial ────► [CHUNKED] (retry)
        │                         │          │
        │                         └─── success ─────► [EMBEDDED]
        │                                               │
        │                                               │  index_kb_document()
        │                                               │  count check → state transition
        │                                               │
        │                                       success─┤
        │                                               │
        │                                               ▼
        │                                          [INDEXED] ◄─── retrievable
        │
        ├─── chunking failed ──────────► [UPLOADED] (stays, event written)
        │
        └─── embedding all failed ─────► [CHUNKED] (stays, event written)
```

```
Retrievability gate:

    generation request
        │
        ▼
    get_kb_style_guidance(db, firm_id, ...)
        │
        ▼
    SELECT ... FROM kb_chunks
    WHERE lifecycle_state = 'indexed'
        │
        ├── results found ──► inject into [KB GUIDANCE BLOCK]
        │                     write kb_guidance_traces
        │                     set kb_guidance_applied = true
        │
        └── no results ─────► return (None, [])
                              kb_guidance_applied = false
                              no kb_guidance_traces written
```

---

## Sequence Diagrams

**Sprint 6A — Synchronous ingestion:**
```
Client          KB Router         pipeline.py        S3 / OpenAI / DB
  │                │                  │                      │
  │  POST /ingest  │                  │                      │
  │───────────────►│                  │                      │
  │                │  chunk_kb_doc()  │                      │
  │                │─────────────────►│   fetch S3 key       │
  │                │                  │─────────────────────►│
  │                │                  │◄─────────────────────│
  │                │                  │   insert KBChunks    │
  │                │                  │─────────────────────►│
  │                │                  │   state→chunked      │
  │                │  embed_kb_doc()  │                      │
  │                │─────────────────►│   embed each chunk   │
  │                │                  │─────────────────────►│
  │                │                  │◄─────────────────────│
  │                │                  │   insert KBEmbeddings│
  │                │                  │   state→embedded     │
  │                │  index_kb_doc()  │                      │
  │                │─────────────────►│   count check        │
  │                │                  │   state→indexed      │
  │                │◄─────────────────│                      │
  │◄───────────────│                  │                      │
  │  200 indexed   │                  │                      │
```

**Sprint 6B — Generation with KB guidance:**
```
Client       Generation       get_kb_style_guidance     DB
  │               │                    │                 │
  │  POST /gen    │                    │                 │
  │──────────────►│                    │                 │
  │               │  assemble evidence │                 │
  │               │────────────────────────────────────►│
  │               │◄────────────────────────────────────│
  │               │                    │                 │
  │               │  call guidance     │                 │
  │               │───────────────────►│  SELECT indexed │
  │               │                    │────────────────►│
  │               │                    │◄────────────────│
  │               │◄───────────────────│                 │
  │               │                    │                 │
  │               │  assemble prompt:  │                 │
  │               │  [EVIDENCE BLOCK]  │                 │
  │               │  [KB GUIDANCE]     │                 │
  │               │                    │                 │
  │               │  LLM call          │                 │
  │               │  write DraftSection                  │
  │               │  write GenerationTrace (evidence)    │
  │               │  write KBGuidanceTrace (guidance)    │
  │◄──────────────│                    │                 │
```

---

## Tradeoffs

| Decision | Benefit | Cost |
|---|---|---|
| Parallel pipeline architecture | Clean separation, independent evolution | Code duplication of chunking/embedding patterns |
| Synchronous endpoint in 6A | Simple QA validation, no queue debugging | Blocking HTTP call for potentially long pipeline |
| Nullable case_id on processing_events | Single event infrastructure | Queries must filter on case_id IS NOT NULL for case-scoped reporting |
| Structural provenance separation | Immune to developer error | Inflexibility if KB evidence ever needs to be cited (requires ADR revision) |
| Lifecycle state as retrievability gate | Deterministic, survives restarts | Documents stuck mid-pipeline require manual re-trigger |

---

## Failure Scenarios

| Scenario | Detection | Recovery |
|---|---|---|
| S3 fetch fails during chunking | `kb_chunking_failed` event, state stays `uploaded` | Fix S3 credentials/key, re-POST `/ingest` |
| OpenAI unavailable during embedding | `kb_embedding_failed` event, state stays `chunked` | ARQ retries 3x with backoff; re-trigger after recovery |
| Partial embedding (some chunks fail) | `kb_embedding_failed` event, partial count in detail | Re-trigger; idempotent — existing embeddings skipped |
| Index check finds missing embeddings | `kb_indexing_failed` event, state stays `embedded` | Re-trigger embed step; index step re-runs after |
| Worker crash mid-pipeline | ARQ retries task from scratch | Pipeline idempotency ensures no duplicate rows |
| firm_id mismatch on task payload | `firm_boundary_violation` returned, task marked failed | Investigate token generation; do not retry without investigation |

---

## Future Extensibility

- **KB document versioning:** The current schema has no version column on `kb_documents`. Future sprints may add versioning to allow firms to update style guides without losing prior guidance history.
- **Per-section KB document targeting:** Currently all `style_guide` and `firm_convention` documents are eligible for any section. Future sprints may add a `section_affinity` column to `kb_documents` to allow firms to target guidance at specific sections.
- **RLS activation:** ADR-009 deferred PostgreSQL Row-Level Security. Once multi-firm production load requires it, the schema (explicit `firm_id` on all KB tables) is already RLS-ready.
- **KB feedback loop:** Future sprints may allow attorneys to flag KB guidance as unhelpful, creating a feedback signal analogous to `classification_feedback`.

---

## Governance Implications

ADR-010 extends the provenance-first principle (ADR-004) into the institutional memory layer. The platform now has two parallel RAG pipelines — evidence RAG and KB RAG — that must remain structurally and operationally separate at all times. This ADR is the formal record of that separation architecture and must be consulted before any Sprint 7+ work touches either pipeline.

**This ADR must not be violated by future ADRs without explicit architectural review.**

---
