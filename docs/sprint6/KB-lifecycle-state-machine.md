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
