This is the full Sprint 6 architecture package. Four artifacts, in order.

---

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

---

# KB Lifecycle State Machine Specification

## States

| State | Meaning | Retrievable by generation |
|---|---|---|
| `uploaded` | File stored in S3, DB row created, no text processing | No |
| `chunked` | Text extracted, KBChunk rows written | No |
| `embedded` | KBEmbedding rows written for all chunks | No |
| `indexed` | Embedding count verified, document is operational | **Yes** |
| `failed` | Pipeline failed at a stage, manual intervention required | No |

## Valid Transitions

```
uploaded  → chunked    (chunk_kb_document succeeds)
uploaded  → failed     (chunk_kb_document fails permanently after retries)
chunked   → embedded   (embed_kb_document succeeds, all chunks embedded)
chunked   → chunked    (embed_kb_document partial — stays, retry eligible)
chunked   → failed     (embed_kb_document fails permanently after retries)
embedded  → indexed    (index_kb_document count check passes)
embedded  → failed     (index_kb_document count check fails permanently)
failed    → uploaded   (manual reset — operator action only)
```

## Invalid Transitions (must never occur)

```
uploaded  → embedded   (chunking cannot be skipped)
uploaded  → indexed    (chunking and embedding cannot be skipped)
chunked   → indexed    (embedding cannot be skipped)
indexed   → any        (indexed is operationally terminal — re-ingestion requires new document)
```

If an invalid transition is detected (e.g., `lifecycle_state = 'indexed'` and chunk count = 0), this is a data integrity violation. Log at ERROR level and alert.

## Idempotency Expectations

Every pipeline function must be safe to call multiple times on the same `kb_document_id`:

- `chunk_kb_document`: if `KBChunk` rows exist → return `{"status": "exists"}`, do not re-chunk
- `embed_kb_document`: for each `KBChunk`, skip if `KBEmbedding` already exists → only embed missing chunks
- `index_kb_document`: count `KBChunk` rows, count `KBEmbedding` rows, compare → if equal, transition to `indexed`; if not, return `failed` with `missing_count`

## Retry Paths

ARQ retries the full `ingest_kb_document` task up to 3 times with exponential backoff. Because each pipeline function is idempotent, retrying from the top of the task is safe — completed stages are skipped, incomplete stages are retried.

```
Attempt 1: chunk(ok) → embed(partial fail, 8/10 chunks) → index(fail, missing 2)
Attempt 2: chunk(exists, skip) → embed(2 missing chunks embedded) → index(ok) → indexed
```

## Recovery Semantics

A document in `failed` state requires operator action. The recovery path is:

1. Operator investigates the `processing_events` record for failure detail
2. Operator corrects the root cause (S3 key, OpenAI quota, embedding dimensions mismatch)
3. Operator resets `lifecycle_state` to the appropriate prior state via admin endpoint or direct DB update
4. Operator re-triggers `POST /kb/documents/{id}/ingest`

There is no automatic recovery from `failed`. Automatic retry without operator review risks repeated API charges or repeated corrupt state writes.

## Terminal States

`indexed` is the operational terminal state. A document that reaches `indexed` is not re-ingested unless the operator explicitly resets it. Re-ingestion is required when the source document changes — the operator uploads a new `kb_document` row rather than modifying the existing one.

`failed` is the error terminal state. It does not automatically recover.

## Retrievability Invariant

```
retrievability ≠ mere existence
```

A KB document exists in the database from the moment `POST /kb/documents` returns 201. It is not retrievable until `lifecycle_state = 'indexed'`. This distinction is enforced by the SQL WHERE clause in `get_kb_style_guidance`:

```sql
AND kc.kb_document_id IN (
    SELECT id FROM kb_documents
    WHERE firm_id = :firm_id
      AND document_type = ANY(:allowed_types)
      AND lifecycle_state = 'indexed'    ← gate
)
```

Removing or weakening this gate is a governed architectural change requiring ADR revision.

## Event Emission Requirements

Every state transition must emit a `ProcessingEvent` row. No transition is silent.

| Transition | Event type | Required detail fields |
|---|---|---|
| `uploaded → chunked` | `kb_chunking_completed` | `chunks_created`, `strategy`, `kb_document_id`, `firm_id` |
| `uploaded → failed` | `kb_chunking_failed` | `reason`, `kb_document_id`, `firm_id` |
| `chunked → embedded` | `kb_embedding_completed` | `embeddings_created`, `model_name`, `kb_document_id` |
| `chunked → chunked` (partial) | `kb_embedding_failed` | `failed_count`, `succeeded_count`, `kb_document_id` |
| `chunked → failed` | `kb_embedding_failed` | `reason`, `kb_document_id` |
| `embedded → indexed` | `kb_indexing_completed` | `indexed_chunks`, `kb_document_id` |
| `embedded → failed` | `kb_indexing_failed` | `missing_count`, `kb_document_id` |

---

---

# Developer Execution Packages

---

## Sprint 6A — Package 1: KB Pipeline Foundation

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 6A, Package 1.
Prerequisite: Sprint 5 fully closed, commit f29a3ae at head.
Run: alembic current → must show 0011_kb_schema (head) before starting.
Read app/ingestion/chunker.py and app/ingestion/embedder.py in full before writing anything.
These files define the patterns you will follow for the KB pipeline.

---

CONTEXT

The KB pipeline mirrors the case document pipeline:
  Case: DocumentVersion.extracted_text_s3_key → Chunk → Embedding
  KB:   KBDocument.s3_key → KBChunk → KBEmbedding

The pattern is the same. The tables are different. The module is separate.

---

TASK 1: Create app/kb/__init__.py

Empty file.

---

TASK 2: Create app/kb/pipeline.py

Create this file. It owns all KB ingestion pipeline logic.

"""KB ingestion pipeline — chunk, embed, index.

Mirrors the case document ingestion pipeline pattern but operates on:
  KBDocument → KBChunk → KBEmbedding

All functions:
  - Validate firm_id before touching any row
  - Are idempotent (safe to call multiple times)
  - Never raise — return status dicts
  - Write ProcessingEvent rows for every transition
  - Advance KBDocument.lifecycle_state atomically with the data write

Public API:
  chunk_kb_document(db, kb_document_id, firm_id) -> dict
  embed_kb_document(db, kb_document_id, firm_id) -> dict
  index_kb_document(db, kb_document_id, firm_id) -> dict
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import openai
from sqlalchemy.orm import Session

from app.core.models import KBChunk, KBDocument, KBEmbedding, ProcessingEvent
from app.ingestion.chunker import chunk_text_paragraph
from app.ingestion.s3 import _bucket, _s3_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_MODEL_VERSION = os.environ.get("EMBEDDING_MODEL_VERSION", "1.0")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", 1536))


def _validate_kb_doc(db: Session, kb_document_id: str, firm_id: str) -> Optional[KBDocument]:
    """Return KBDocument if it exists and belongs to firm_id, else None."""
    return (
        db.query(KBDocument)
        .filter(
            KBDocument.id == kb_document_id,
            KBDocument.firm_id == firm_id,
        )
        .first()
    )


def _write_kb_event(
    db: Session,
    event_type: str,
    status: str,
    kb_document_id: str,
    firm_id: str,
    detail: dict,
    error_message: Optional[str] = None,
) -> None:
    """Write a ProcessingEvent for a KB pipeline stage. case_id is None."""
    event = ProcessingEvent(
        case_id=None,
        document_id=None,
        document_version_id=None,
        event_type=event_type,
        status=status,
        detail={"kb_document_id": kb_document_id, "firm_id": firm_id, **detail},
        error_message=error_message,
    )
    db.add(event)
    db.commit()


def chunk_kb_document(db: Session, kb_document_id: str, firm_id: str) -> dict:
    """Extract text from S3, chunk using paragraph strategy, persist KBChunk rows.

    Lifecycle: uploaded → chunked
    Idempotent: returns {"status": "exists"} if KBChunk rows already present.
    Never raises.
    """
    try:
        kb_doc = _validate_kb_doc(db, kb_document_id, firm_id)
        if kb_doc is None:
            return {"status": "failed", "reason": "firm_boundary_violation"}

        # Idempotency check
        from sqlalchemy import func
        existing_count = (
            db.query(func.count(KBChunk.id))
            .filter(KBChunk.kb_document_id == kb_document_id)
            .scalar()
        ) or 0
        if existing_count > 0:
            return {"status": "exists", "chunks_created": existing_count}

        # Fetch text from S3
        try:
            response = _s3_client().get_object(Bucket=_bucket(), Key=kb_doc.s3_key)
            raw_bytes = response["Body"].read()
            text = raw_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            _write_kb_event(
                db, "kb_chunking_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "s3_fetch_failed"},
                error_message=str(exc),
            )
            return {"status": "failed", "reason": "s3_fetch_failed"}

        if not text.strip():
            _write_kb_event(
                db, "kb_chunking_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "empty_text"},
                error_message="Extracted text is empty after strip",
            )
            return {"status": "failed", "reason": "empty_text"}

        pieces = chunk_text_paragraph(text)
        if not pieces:
            _write_kb_event(
                db, "kb_chunking_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "no_chunks_produced"},
            )
            return {"status": "failed", "reason": "no_chunks_produced"}

        chunk_objects = [
            KBChunk(
                id=str(uuid.uuid4()),
                firm_id=firm_id,
                kb_document_id=kb_document_id,
                chunk_index=p["chunk_index"],
                text=p["text"],
                chunk_strategy="paragraph",
            )
            for p in pieces
        ]
        db.bulk_save_objects(chunk_objects)

        kb_doc.lifecycle_state = "chunked"
        kb_doc.updated_at = datetime.utcnow()

        _write_kb_event(
            db, "kb_chunking_completed", "completed",
            kb_document_id, firm_id,
            {"chunks_created": len(pieces), "strategy": "paragraph"},
        )

        return {"status": "ok", "chunks_created": len(pieces)}

    except Exception as exc:
        logger.exception("chunk_kb_document failed kb_document_id=%s", kb_document_id)
        try:
            db.rollback()
        except Exception:
            pass
        _write_kb_event(
            db, "kb_chunking_failed", "failed",
            kb_document_id, firm_id,
            {"reason": "exception"},
            error_message=str(exc),
        )
        return {"status": "failed", "reason": str(exc)}


def embed_kb_document(db: Session, kb_document_id: str, firm_id: str) -> dict:
    """Embed all KBChunk rows, persist KBEmbedding rows.

    Lifecycle: chunked → embedded
    Idempotent: skips chunks that already have an embedding.
    Partial success keeps state at 'chunked' — retry will complete remaining.
    Never raises.
    """
    try:
        kb_doc = _validate_kb_doc(db, kb_document_id, firm_id)
        if kb_doc is None:
            return {"status": "failed", "reason": "firm_boundary_violation"}

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"status": "failed", "reason": "missing_api_key"}

        chunks = (
            db.query(KBChunk)
            .filter(
                KBChunk.kb_document_id == kb_document_id,
                KBChunk.firm_id == firm_id,
            )
            .order_by(KBChunk.chunk_index.asc())
            .all()
        )
        if not chunks:
            return {"status": "failed", "reason": "no_chunks"}

        client = openai.OpenAI(api_key=api_key)
        succeeded = 0
        failed = 0
        skipped = 0

        for chunk in chunks:
            existing = (
                db.query(KBEmbedding)
                .filter(KBEmbedding.kb_chunk_id == chunk.id)
                .first()
            )
            if existing:
                skipped += 1
                continue

            try:
                response = client.embeddings.create(
                    input=chunk.text,
                    model=EMBEDDING_MODEL,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
                vector = response.data[0].embedding
            except Exception as embed_exc:
                logger.exception("KB embedding failed for chunk %s", chunk.id)
                failed += 1
                continue

            db.add(KBEmbedding(
                id=str(uuid.uuid4()),
                firm_id=firm_id,
                kb_chunk_id=chunk.id,
                embedding=vector,
                model_name=EMBEDDING_MODEL,
            ))
            succeeded += 1

        if succeeded == 0 and failed > 0:
            try:
                db.rollback()
            except Exception:
                pass
            _write_kb_event(
                db, "kb_embedding_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "all_chunks_failed", "failed_count": failed},
            )
            return {"status": "failed", "reason": "all_chunks_failed"}

        if failed > 0:
            # Partial — commit what succeeded, stay at chunked
            db.commit()
            _write_kb_event(
                db, "kb_embedding_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "partial", "succeeded_count": succeeded, "failed_count": failed},
            )
            return {"status": "partial", "embeddings_created": succeeded, "failed_count": failed}

        kb_doc.lifecycle_state = "embedded"
        kb_doc.updated_at = datetime.utcnow()
        db.commit()

        _write_kb_event(
            db, "kb_embedding_completed", "completed",
            kb_document_id, firm_id,
            {"embeddings_created": succeeded, "model_name": EMBEDDING_MODEL},
        )
        return {"status": "ok", "embeddings_created": succeeded}

    except Exception as exc:
        logger.exception("embed_kb_document failed kb_document_id=%s", kb_document_id)
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "failed", "reason": str(exc)}


def index_kb_document(db: Session, kb_document_id: str, firm_id: str) -> dict:
    """Verify all chunks have embeddings and advance lifecycle to indexed.

    Lifecycle: embedded → indexed
    Idempotent: safe to call if already indexed.
    Never raises.
    """
    try:
        kb_doc = _validate_kb_doc(db, kb_document_id, firm_id)
        if kb_doc is None:
            return {"status": "failed", "reason": "firm_boundary_violation"}

        if kb_doc.lifecycle_state == "indexed":
            return {"status": "ok", "note": "already_indexed"}

        from sqlalchemy import func
        chunk_count = (
            db.query(func.count(KBChunk.id))
            .filter(KBChunk.kb_document_id == kb_document_id)
            .scalar()
        ) or 0

        embedding_count = (
            db.query(func.count(KBEmbedding.id))
            .join(KBChunk, KBChunk.id == KBEmbedding.kb_chunk_id)
            .filter(KBChunk.kb_document_id == kb_document_id)
            .scalar()
        ) or 0

        if chunk_count == 0:
            _write_kb_event(
                db, "kb_indexing_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "no_chunks", "chunk_count": 0},
            )
            return {"status": "failed", "reason": "no_chunks"}

        if embedding_count < chunk_count:
            missing = chunk_count - embedding_count
            _write_kb_event(
                db, "kb_indexing_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "embedding_incomplete", "missing_count": missing,
                 "chunk_count": chunk_count, "embedding_count": embedding_count},
            )
            return {"status": "failed", "reason": "embedding_incomplete", "missing_count": missing}

        kb_doc.lifecycle_state = "indexed"
        kb_doc.updated_at = datetime.utcnow()
        db.commit()

        _write_kb_event(
            db, "kb_indexing_completed", "completed",
            kb_document_id, firm_id,
            {"indexed_chunks": chunk_count},
        )
        return {"status": "ok", "indexed_chunks": chunk_count}

    except Exception as exc:
        logger.exception("index_kb_document failed kb_document_id=%s", kb_document_id)
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "failed", "reason": str(exc)}

---

TASK 3: Add POST /kb/documents/{kb_document_id}/ingest to app/api/kb/router.py

Add this endpoint after the existing search endpoint.

@router.post("/kb/documents/{kb_document_id}/ingest", status_code=200)
def ingest_kb_document_sync(
    *,
    kb_document_id: str,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Run KB ingestion pipeline synchronously (Sprint 6A).

    Progresses the KB document through:
      uploaded → chunked → embedded → indexed

    Returns final lifecycle_state and per-stage results.
    Sprint 6B migrates this to an async ARQ task.
    """
    from app.kb.pipeline import chunk_kb_document, embed_kb_document, index_kb_document

    kb_doc = _get_kb_document(db, kb_document_id, claims.firm_id)
    if kb_doc is None:
        raise HTTPException(status_code=404, detail="KB document not found")

    if kb_doc.lifecycle_state == "indexed":
        return {"status": "already_indexed", "lifecycle_state": "indexed"}

    results = {}

    if kb_doc.lifecycle_state == "uploaded":
        result = chunk_kb_document(db, kb_document_id, claims.firm_id)
        results["chunking"] = result
        db.refresh(kb_doc)
        if result["status"] not in ("ok", "exists"):
            return {
                "status": "failed",
                "stage": "chunking",
                "lifecycle_state": kb_doc.lifecycle_state,
                "results": results,
            }

    if kb_doc.lifecycle_state == "chunked":
        result = embed_kb_document(db, kb_document_id, claims.firm_id)
        results["embedding"] = result
        db.refresh(kb_doc)
        if result["status"] == "failed":
            return {
                "status": "failed",
                "stage": "embedding",
                "lifecycle_state": kb_doc.lifecycle_state,
                "results": results,
            }

    if kb_doc.lifecycle_state == "embedded":
        result = index_kb_document(db, kb_document_id, claims.firm_id)
        results["indexing"] = result
        db.refresh(kb_doc)
        if result["status"] != "ok":
            return {
                "status": "failed",
                "stage": "indexing",
                "lifecycle_state": kb_doc.lifecycle_state,
                "results": results,
            }

    return {
        "status": "ok",
        "lifecycle_state": kb_doc.lifecycle_state,
        "results": results,
    }

---

TASK 4: Validate (no server required)

Run:
  python3 -c "from app.kb.pipeline import chunk_kb_document, embed_kb_document, index_kb_document; print('import ok')"

Must print "import ok" without error.

Run:
  grep -rn "from app.kb" app/
  grep -rn "import pipeline" app/kb/

Report output.

---

TASK 5: Commit

git add app/kb/
git add app/api/kb/router.py
git commit -m "feat(kb): KB ingestion pipeline — chunk, embed, index (Sprint 6A Package 1)

Implements app/kb/pipeline.py with three pipeline functions:
  chunk_kb_document: S3 fetch → paragraph split → KBChunk rows
  embed_kb_document: OpenAI embed → KBEmbedding rows
  index_kb_document: count check → lifecycle_state = 'indexed'

All functions: firm-validated, idempotent, never raise, emit ProcessingEvents.
Lifecycle gate: retrievable iff lifecycle_state = 'indexed'.

POST /kb/documents/{id}/ingest added — runs pipeline synchronously (6A).
Sprint 6B migrates to async ARQ enqueue."
git push origin May26

Stop. Report commit hash. Do not begin Package 2 until QA signs off.
```

---

## Sprint 6A — Package 2: ARQ + Async Operationalization

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 6A, Package 2.
Prerequisite: Package 1 committed and QA signed off.
Read app/workers/tasks.py and app/workers/enqueue.py in full before writing.

---

CONTEXT

Package 2 replaces the ingest_kb_document stub in tasks.py with the real
pipeline, and adds an enqueue helper. The synchronous /ingest endpoint
remains unchanged — Package 2 only operationalizes the async path.

---

TASK 1: Update app/workers/tasks.py — replace ingest_kb_document stub

Find the ingest_kb_document function. Replace the stub body with:

    db: Session = SessionLocal()
    try:
        kb_doc = db.query(KBDocument).filter(
            KBDocument.id == kb_document_id,
            KBDocument.firm_id == firm_id,
        ).first()
        if kb_doc is None:
            logger.error(
                "ingest_kb_document: firm_id mismatch or not found "
                "kb_document_id=%s firm_id=%s", kb_document_id, firm_id
            )
            return {"status": "failed", "reason": "firm_boundary_violation"}

        from app.kb.pipeline import chunk_kb_document, embed_kb_document, index_kb_document

        result = chunk_kb_document(db, kb_document_id, firm_id)
        if result["status"] not in ("ok", "exists"):
            return {"status": "failed", "reason": f"chunking: {result.get('reason')}"}

        result = embed_kb_document(db, kb_document_id, firm_id)
        if result["status"] == "failed":
            return {"status": "failed", "reason": f"embedding: {result.get('reason')}"}

        result = index_kb_document(db, kb_document_id, firm_id)
        if result["status"] != "ok":
            return {"status": "failed", "reason": f"indexing: {result.get('reason')}"}

        return {"status": "ok", "kb_document_id": kb_document_id}
    except Exception as exc:
        logger.exception("ingest_kb_document failed kb_document_id=%s", kb_document_id)
        return {"status": "failed", "reason": str(exc)}
    finally:
        db.close()

Remove the comment "# Stub: KB chunking/embedding pipeline not yet implemented."

---

TASK 2: Update app/workers/enqueue.py — confirm enqueue_ingest_kb_document exists

Check that enqueue_ingest_kb_document already exists in enqueue.py.
If it does, make no changes.
If it does not, add it:

  async def enqueue_ingest_kb_document(
      pool,
      *,
      kb_document_id: str,
      firm_id: str,
  ) -> str:
      job = await pool.enqueue_job(
          "ingest_kb_document",
          kb_document_id=kb_document_id,
          firm_id=firm_id,
          _queue_name="llm_tasks",
      )
      return job.job_id

---

TASK 3: Validate import chain

Run from the web container or locally:
  python3 -c "
  from app.workers.tasks import ingest_kb_document
  from app.kb.pipeline import chunk_kb_document
  print('import chain ok')
  "

Must print "import chain ok".

Run:
  grep -n "pipeline_stub" app/workers/tasks.py

Must return zero matches — the stub comment is gone.

---

TASK 4: Commit

git add app/workers/tasks.py
git add app/workers/enqueue.py
git commit -m "feat(workers): replace ingest_kb_document stub with real pipeline (Sprint 6A Package 2)

ARQ task now executes chunk → embed → index pipeline via app/kb/pipeline.py.
Firm boundary validation retained. Idempotency preserved across retries.
Stub comment removed."
git push origin May26

Stop. Report commit hash. Do not begin Package 3 until QA signs off.
```

---

## Sprint 6A — Package 3: Observability + Events

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 6A, Package 3.
Prerequisite: Package 2 committed and QA signed off.
Read app/core/models.py and app/ingestion/events.py in full before writing.

---

TASK 1: Create migration 0012

Create: alembic/versions/0012_nullable_case_id.py
down_revision = "0011_kb_schema"

upgrade():
  op.execute(text("ALTER TABLE processing_events ALTER COLUMN case_id DROP NOT NULL"))

downgrade():
  # Backfill any null case_id rows before re-adding NOT NULL
  # Use a sentinel case_id that will not conflict with real data
  op.execute(text(
      "UPDATE processing_events SET case_id = '00000000-0000-0000-0000-000000000000' "
      "WHERE case_id IS NULL"
  ))
  op.execute(text("ALTER TABLE processing_events ALTER COLUMN case_id SET NOT NULL"))

---

TASK 2: Update ProcessingEvent model in app/core/models.py

Find case_id column on ProcessingEvent. Change nullable=False to nullable=True.
Update the model docstring to note that case_id is null for KB pipeline events.

---

TASK 3: Update app/ingestion/events.py

Find the write_event function signature. Make case_id Optional[str] with default None.
No other changes — the function body already passes case_id through to the model.

If case_id is not currently in the function signature, inspect the file first and
report what you find before making any changes.

---

TASK 4: Add GET /kb/documents/{kb_document_id}/events to app/api/kb/router.py

@router.get("/kb/documents/{kb_document_id}/events")
def get_kb_document_events(
    *,
    kb_document_id: str,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Return all pipeline events for a KB document.

    Firm-scoped: confirms kb_document belongs to claims.firm_id before
    returning events. Events are identified by kb_document_id in detail JSONB.
    """
    from app.core.models import ProcessingEvent
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB

    kb_doc = _get_kb_document(db, kb_document_id, claims.firm_id)
    if kb_doc is None:
        raise HTTPException(status_code=404, detail="KB document not found")

    events = (
        db.query(ProcessingEvent)
        .filter(
            ProcessingEvent.detail["kb_document_id"].astext == kb_document_id
        )
        .order_by(ProcessingEvent.created_at.asc())
        .all()
    )

    return {
        "kb_document_id": kb_document_id,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "status": e.status,
                "detail": e.detail,
                "error_message": e.error_message,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }

---

TASK 5: Apply migration and validate

Run:
  alembic upgrade head

Confirm: 0012_nullable_case_id is head.

Run:
  SELECT column_name, is_nullable FROM information_schema.columns
  WHERE table_name = 'processing_events' AND column_name = 'case_id';

Must return is_nullable = YES.

---

TASK 6: End-to-end validation

Using token 1, run the full pipeline:
  POST /kb/documents (upload a small text file)
  POST /kb/documents/{id}/ingest
  GET /kb/documents/{id}/events

Confirm:
- /ingest returns lifecycle_state = 'indexed'
- /events returns at least: kb_chunking_completed, kb_embedding_completed, kb_indexing_completed
- GET /kb/documents/{id} shows chunk_count > 0

---

TASK 7: Commit

git add alembic/versions/0012_nullable_case_id.py
git add app/core/models.py
git add app/ingestion/events.py
git add app/api/kb/router.py
git commit -m "feat(observability): nullable case_id on processing_events, KB pipeline events, /events endpoint (Sprint 6A Package 3)

Migration 0012 makes processing_events.case_id nullable, unblocking KB
pipeline event writes. KB events use detail JSONB for kb_document_id.
GET /kb/documents/{id}/events provides operator pipeline visibility.
ProcessingEvent model and write_event() updated for nullable case_id."
git push origin May26

Sprint 6A is complete after QA signs off on this commit.
Stop. Do not begin Sprint 6B until Sprint 6A QA closure.
```

---

## Sprint 6B — Package 1: Controlled KB Influence

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 6B, Package 1.
Prerequisite: Sprint 6A fully closed. At least one KB document in
lifecycle_state = 'indexed' for the QA firm. Confirm before starting:

  SELECT id, lifecycle_state FROM kb_documents
  WHERE firm_id = '8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b'
  AND lifecycle_state = 'indexed';

Must return at least 1 row. If 0 rows, run POST /kb/documents/{id}/ingest
on an existing KB document before proceeding.

---

CONTEXT

get_kb_style_guidance in app/generation/templates.py is already implemented.
It returns (None, []) when no indexed KB documents exist.
Once indexed documents exist, it fires automatically — no code change required
for the retrieval itself.

Package 1 scope:
1. Add the KB guidance system prompt instruction to prompt_templates via migration
2. Update the POST /kb/documents/{id}/ingest endpoint to enqueue async (ARQ)
3. Validate end-to-end KB guidance injection in a real generation run

---

TASK 1: Create migration 0013 — add KB guidance instruction to system prompts

Create: alembic/versions/0013_kb_guidance_prompt_instruction.py
down_revision = "0012_nullable_case_id"

This migration appends a KB guidance instruction to all active EB2 system prompts.
It does NOT replace the system prompts — it appends to them.

The instruction to append (add a newline before it):

STYLE_GUIDANCE_INSTRUCTION = """

IMPORTANT: If style guidance is provided below in a [KB STYLE GUIDANCE] block,
it is for rhetorical conditioning only. It must not be cited as evidence,
attributed to the petitioner, or presented as factual support for any claim.
Evidence is provided separately in the Evidence block and is the only permitted
source of factual claims in this section."""

upgrade():
  conn = op.get_bind()
  conn.execute(text(
      "UPDATE prompt_templates "
      "SET system_prompt = system_prompt || :instruction "
      "WHERE visa_type = 'EB2' AND is_active = true "
      "AND system_prompt NOT LIKE '%%rhetorical conditioning%%'"
  ), {"instruction": STYLE_GUIDANCE_INSTRUCTION})

downgrade():
  conn = op.get_bind()
  conn.execute(text(
      "UPDATE prompt_templates "
      "SET system_prompt = REPLACE(system_prompt, :instruction, '') "
      "WHERE visa_type = 'EB2'"
  ), {"instruction": STYLE_GUIDANCE_INSTRUCTION})

---

TASK 2: Update POST /kb/documents/{id}/ingest to enqueue async

In app/api/kb/router.py, update ingest_kb_document_sync:
- Rename to ingest_kb_document_endpoint
- Change to async def
- Replace the synchronous pipeline calls with an ARQ enqueue:

  from app.workers.enqueue import get_arq_pool, enqueue_ingest_kb_document

  pool = await get_arq_pool()
  job_id = await enqueue_ingest_kb_document(
      pool,
      kb_document_id=kb_document_id,
      firm_id=claims.firm_id,
  )
  await pool.aclose()

- Change status_code to 202
- Return: {"status": "queued", "job_id": job_id, "kb_document_id": kb_document_id}
- Add note: poll GET /kb/documents/{id} for lifecycle_state = 'indexed'

---

TASK 3: Apply migration 0013 and validate

Run:
  alembic upgrade head

Confirm 0013_kb_guidance_prompt_instruction is head.

Run:
  SELECT section_code, length(system_prompt),
         system_prompt LIKE '%%rhetorical conditioning%%' AS has_instruction
  FROM prompt_templates
  WHERE visa_type = 'EB2' AND is_active = true
  ORDER BY section_code;

Must return has_instruction = true for all 6 rows.

---

TASK 4: End-to-end KB guidance injection validation

With at least one indexed KB document for the QA firm, run generation:

  POST /cases/129ecb0a-86d0-451c-a447-cc7bb5ab8269/generate
  body: {document_id: <any indexed doc id>, visa_type: "EB2", force_generate: true}
  Authorization: Bearer <token1>

Record the draft_id. Then run:

  SELECT kb_guidance_applied FROM draft_sections
  WHERE draft_output_id = '<draft_id>'
  ORDER BY created_at;

Report: how many sections have kb_guidance_applied = true.

  SELECT COUNT(*) FROM kb_guidance_traces
  WHERE firm_id = '8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b';

Report count.

If both are 0 (no KB guidance fired), check:
  SELECT lifecycle_state FROM kb_documents
  WHERE firm_id = '8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b';

All must be 'indexed'. If any are not indexed, run POST /kb/documents/{id}/ingest
synchronously (call the pipeline functions directly) and retry.

---

TASK 5: Commit

git add alembic/versions/0013_kb_guidance_prompt_instruction.py
git add app/api/kb/router.py
git commit -m "feat(generation): KB guidance prompt instruction + async ingest endpoint (Sprint 6B Package 1)

Migration 0013 appends rhetorical conditioning instruction to all active EB2
system prompts. Instruction explicitly labels KB guidance as advisory and
prohibits citation as evidence.

POST /kb/documents/{id}/ingest now enqueues ARQ task (async, 202 Accepted).
Callers poll GET /kb/documents/{id} for lifecycle_state = 'indexed'."
git push origin May26

Stop. Report commit hash and Task 4 validation results.
Do not begin Package 2 until QA signs off.
```

---

## Sprint 6B — Package 2: Provenance Separation Enforcement

```
You are the Developer on LegalLanguageModels, branch May26.

This is Sprint 6B, Package 2.
Prerequisite: Package 1 committed and QA signed off.
At least one generation run must have completed with kb_guidance_applied = true
on at least one draft_section.

---

CONTEXT

This package validates that the provenance separation invariant holds
structurally and operationally. It adds no new features. It makes the
invariant permanently verifiable and adds a QA endpoint for ongoing validation.

---

TASK 1: Create app/api/kb/invariants.py

"""Provenance separation invariant checks.

These queries validate that KB guidance has never entered evidentiary
provenance chains. They are intended for QA, CI, and operational auditing.

The core invariant:

  SELECT COUNT(*) FROM generation_traces gt
  JOIN kb_chunks kc ON kc.id = gt.chunk_id;

Must always return 0.

This is a permanent platform invariant. It cannot be relaxed without
revising ADR-004 and ADR-010 through formal architectural review.

Why this is permanent:
  generation_traces records evidence provenance — the chain from a classified
  document chunk to a draft section. This chain is the platform's legal audit
  trail. If KB chunk IDs ever appear in this chain, the audit trail becomes
  legally unreliable: a USCIS adjudicator reading a generation trace would
  believe firm-internal style preferences are case evidence.

  The structural separation (separate FK targets, no shared chunk namespace)
  is the mechanical enforcement. This query is the verification.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text


def check_provenance_separation(db: Session) -> dict:
    """Verify KB chunks have never entered generation_traces.

    Returns:
      {"status": "ok", "violation_count": 0} — invariant holds
      {"status": "violated", "violation_count": N} — CRITICAL — alert immediately
    """
    result = db.execute(text(
        """
        SELECT COUNT(*) FROM generation_traces gt
        JOIN kb_chunks kc ON kc.id = gt.chunk_id
        """
    )).scalar()

    count = int(result or 0)
    if count == 0:
        return {"status": "ok", "violation_count": 0}
    return {
        "status": "violated",
        "violation_count": count,
        "message": (
            "CRITICAL: KB chunk IDs found in generation_traces. "
            "Evidence provenance chain is compromised. "
            "Halt generation and investigate immediately."
        ),
    }


def check_kb_guidance_trace_isolation(db: Session) -> dict:
    """Verify kb_guidance_traces has no chunk or classification FKs.

    This is a schema check — if the columns exist, the invariant is violated.
    Returns:
      {"status": "ok"} — columns do not exist
      {"status": "violated", "forbidden_columns": [...]} — CRITICAL
    """
    result = db.execute(text(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'kb_guidance_traces'
          AND column_name IN ('chunk_id', 'classification_result_id')
        """
    )).fetchall()

    forbidden = [row[0] for row in result]
    if not forbidden:
        return {"status": "ok"}
    return {
        "status": "violated",
        "forbidden_columns": forbidden,
        "message": (
            "CRITICAL: kb_guidance_traces contains forbidden FK columns. "
            "Schema integrity violated."
        ),
    }


def check_cross_firm_kb_access(db: Session, firm_id: str) -> dict:
    """Verify all KB chunks for this firm are isolated to this firm.

    Returns count of kb_chunks where firm_id does not match kb_document.firm_id.
    Must always return 0.
    """
    result = db.execute(text(
        """
        SELECT COUNT(*) FROM kb_chunks kc
        JOIN kb_documents kd ON kd.id = kc.kb_document_id
        WHERE kc.firm_id != kd.firm_id
          AND (kc.firm_id = :firm_id OR kd.firm_id = :firm_id)
        """
    ), {"firm_id": firm_id}).scalar()

    count = int(result or 0)
    if count == 0:
        return {"status": "ok", "violation_count": 0}
    return {
        "status": "violated",
        "violation_count": count,
        "message": "CRITICAL: KB chunk firm_id does not match parent document firm_id.",
    }

---

TASK 2: Add GET /kb/invariants to app/api/kb/router.py

from app.api.kb.invariants import (
    check_provenance_separation,
    check_kb_guidance_trace_isolation,
    check_cross_firm_kb_access,
)

@router.get("/kb/invariants")
def check_kb_invariants(
    *,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    """Run all KB provenance separation invariant checks.

    Returns pass/fail for each invariant. Any 'violated' status is CRITICAL.
    Intended for QA, CI health checks, and operational auditing.
    """
    return {
        "firm_id": claims.firm_id,
        "checks": {
            "provenance_separation": check_provenance_separation(db),
            "kb_guidance_trace_isolation": check_kb_guidance_trace_isolation(db),
            "cross_firm_kb_access": check_cross_firm_kb_access(db, claims.firm_id),
        },
    }

---

TASK 3: Run all invariant checks against QA database

Call:
  GET /kb/invariants
  Authorization: Bearer <token1>

Report the full response. All three checks must return status = "ok".

If any check returns "violated", stop immediately and report to the architect.
Do not commit. Do not proceed.

---

TASK 4: Run negative invariant test

Confirm the provenance_separation check would detect a violation.
Run this query directly against the database:

  SELECT COUNT(*) FROM generation_traces gt
  JOIN kb_chunks kc ON kc.id = gt.chunk_id;

Must return 0. Report the result verbatim.

Also confirm:
  SELECT column_name FROM information_schema.columns
  WHERE table_name = 'kb_guidance_traces'
    AND column_name IN ('chunk_id', 'classification_result_id');

Must return 0 rows. Report verbatim.

---

TASK 5: Commit

git add app/api/kb/invariants.py
git add app/api/kb/router.py
git commit -m "feat(governance): KB provenance separation invariant checks (Sprint 6B Package 2)

Adds app/api/kb/invariants.py with three structural checks:
  - provenance_separation: generation_traces must never contain KB chunk IDs
  - kb_guidance_trace_isolation: kb_guidance_traces must never have chunk/CR FKs
  - cross_firm_kb_access: KB chunk firm_id must match parent document firm_id

GET /kb/invariants endpoint exposes all checks for QA and CI.
All checks validated against QA database — all pass."
git push origin May26

Sprint 6B is complete after QA signs off on this commit.
```

---

---

# Platform Provenance Separation Principles

**Document type:** Architectural Constitution
**Status:** Ratified at Sprint 6
**Superseded by:** Nothing — this document may only be amended by unanimous architect + PO review
**Governs:** All future ADRs, sprint plans, and implementation decisions touching evidence, KB, generation, or tracing

---

## Preamble

LegalLanguageModels is not a generic RAG system. It is provenance-preserving institutional legal intelligence infrastructure. The platform generates legal arguments that will be read by USCIS adjudicators, attorneys, and petitioners. The trustworthiness of those arguments depends entirely on the integrity of the evidence chain from source document to generated draft.

This document defines the permanent constitutional rules of the platform. These rules exist not because they are technically convenient but because they are legally and ethically necessary. A generated legal argument that cites institutional style preferences as case evidence is not a mistake — it is a misrepresentation. The platform must make that misrepresentation structurally impossible.

---

## Principle 1: KB guidance never becomes evidence

KB documents contain firm-internal institutional knowledge: style preferences, rhetorical conventions, precedent letter structures. This material informs how the platform writes. It does not inform what the platform claims is true about a petitioner.

**Operational definition:** KB guidance is injected into the generation prompt in a clearly delimited `[KB STYLE GUIDANCE]` block. The system prompt explicitly instructs the LLM that this block is advisory and must not be cited as evidence. KB guidance chunk IDs never appear in `generation_traces`.

**Verification query:**
```sql
SELECT COUNT(*) FROM generation_traces gt
JOIN kb_chunks kc ON kc.id = gt.chunk_id;
```
Must always return 0. Permanently.

---

## Principle 2: Evidence provenance is immutable

`generation_traces` records the chain from a classified document chunk to a draft section. Once written, these rows are never updated or deleted. They are the platform's legal audit trail.

**Operational definition:** `generation_traces` carries `{info: {append_only: True}}` on the ORM model. No UPDATE or DELETE statement may be issued against this table anywhere in the codebase. Feedback and corrections create new rows in `classification_feedback` — they do not modify existing trace rows.

---

## Principle 3: Evidence systems and guidance systems remain structurally separate

`generation_traces` has FK constraints to `chunks` and `classification_results`.
`kb_guidance_traces` has FK constraints to `kb_chunks` and `draft_sections`.

These two tables share no FK targets. There is no column that could accidentally link them. This separation is enforced at the schema layer and survives code changes, developer turnover, and sprint pressure.

**Forbidden schema changes (require ADR revision):**
- Adding `chunk_id` or `classification_result_id` to `kb_guidance_traces`
- Adding `kb_chunk_id` to `generation_traces`
- Creating any FK relationship between the evidence tables and the KB tables

---

## Principle 4: Cross-firm access is forbidden

No evidence, KB material, draft, trace, feedback, classification result, retrieval result, or citation_text may cross `firm_id` boundaries under any code path, query, or API call.

**Operational definition:** Every DB query that touches case-scoped or KB-scoped data must carry an explicit `firm_id` predicate. pgvector similarity queries use raw SQL with `firm_id` in the WHERE clause. JWT tokens without `firm_id` are rejected 401. Cross-firm case access returns 404, not 403 — resource existence must not be disclosed across firm boundaries.

---

## Principle 5: Retrieval is governance-first

KB retrieval uses symbolic filtering before semantic ranking. Document type constraints (`style_guide`, `firm_convention`, `precedent_letter`) are applied as a WHERE clause before the pgvector similarity search runs. Semantic ranking operates only within the symbolically filtered candidate set.

**Rationale:** Semantic-only retrieval can surface KB material from unintended document types. A precedent letter retrieved for a style guidance query would contaminate the guidance with case-specific facts from a prior matter. The symbolic gate prevents this.

---

## Principle 6: Lifecycle state governs retrievability

A KB document is retrievable if and only if `lifecycle_state = 'indexed'`. Documents in `uploaded`, `chunked`, or `embedded` states are not retrievable regardless of what data exists in child tables.

**Operational definition:** The `get_kb_style_guidance` SQL query carries `AND lifecycle_state = 'indexed'` in its subquery. This clause must not be removed or weakened. If it is ever absent from the query, that is a governed architectural regression.

---

## Principle 7: Provenance integrity overrides generation completeness

If evidence is insufficient for a section, the platform returns a sentinel value (`INSUFFICIENT EVIDENCE`) rather than generating unsupported content. The platform does not hallucinate, infer, or supplement with KB material to fill evidentiary gaps.

**Operational definition:** `_generate_section` in `generation/service.py` checks evidence results before calling the LLM. If `evidence_results` is empty and `section_code != 'conclusion'`, the sentinel is written and no LLM call is made. KB guidance does not substitute for missing evidence.

---

## Principle 8: Omission is preferred over unsupported generation

When the platform cannot generate a section with evidence-bound content, it omits rather than fabricates. A draft with one sentinel section and five evidence-bound sections is preferable to a draft with six sections where one contains unsupported claims.

**Operational definition:** This principle applies to all future generation features. Any proposed feature that generates content without traceable evidence must be refused unless it is explicitly labeled as non-evidentiary (as KB guidance is) and stored in a separate trace table.

---

## Amendment Process

These principles may only be amended by:

1. A new ADR that explicitly identifies which principle is being amended and why
2. Architect sign-off
3. PO formal acceptance
4. QA validation that the amendment does not create provenance violations

No sprint plan, implementation prompt, or developer decision may override these principles without completing this process.

---

**This document is the architectural constitution of LegalLanguageModels. All future work is subordinate to it.**
