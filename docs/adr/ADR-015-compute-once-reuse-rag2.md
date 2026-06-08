# ADR-015: Compute Once, Reuse Many — RAG 2 KB Template Deduplication

**Status:** Accepted
**Date:** 2026-06-07
**Supersedes:** N/A
**Superseded by:** N/A
**Scope:** RAG 2 (`kb_templates`) only. RAG 1 evidence pipeline untouched.

## Context

The `extract_kb_templates` ARQ task runs LLM extraction for every `kb_chunk` × `section_key` combination. Without idempotency protection:

- Re-runs after quota exhaustion re-extract completed chunks
- Duplicate `kb_template` rows are created for the same `(kb_chunk_id, section_key)`
- OpenAI costs scale with retries, not with unique work

Two failed extraction runs already created duplicate rows in `kb_templates`.

## Decision

Apply **Compute Once, Reuse Many** scoped to `kb_templates` for MVP.

Three changes:

1. **Unique constraint on `kb_templates(kb_chunk_id, section_key)`**
   Enforced at the PostgreSQL level. Prevents duplicate rows regardless of how many times extraction runs.

2. **Content hash on `kb_templates`**
   SHA-256 of normalized chunk text. Enables future deduplication across documents with identical content. Stored but not yet used for cross-document lookup.

3. **Idempotency check in `extract_kb_template`**
   Before any LLM call, check if a row already exists for `(kb_chunk_id, section_key)`. If yes, return existing template ID. LLM call is skipped entirely.

## Architecture

### Normalization

```
normalize(text) = text.strip().lower() with collapsed whitespace
content_hash = SHA-256(normalize(text))
```

### Idempotency flow

```
extract_kb_template(kb_chunk_id, section_key)
  → normalize chunk text
  → compute content_hash
  → check kb_templates WHERE kb_chunk_id = ? AND section_key = ?
  → if exists: return {status: "exists", kb_template_id: existing.id}
  → if not: call LLM → parse JSON → write KBTemplate row
  → PostgreSQL unique constraint is final safety net
```

### Deduplication guarantee

- **Service logic:** skip if row exists (optimization)
- **DB constraint:** `UNIQUE(kb_chunk_id, section_key)`
