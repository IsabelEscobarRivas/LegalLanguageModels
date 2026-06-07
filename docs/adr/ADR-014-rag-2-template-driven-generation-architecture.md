# ADR-014: RAG 2 Template-Driven Generation Architecture

**Status:** Accepted
**Date:** 2026-06-02
**Supersedes:** [ADR-008](ADR-008-taxonomy-aware-kb-retrieval.md) (Taxonomy-aware KB retrieval on `kb_chunks`)
**Superseded by:** N/A

## Context

LegalLanguageModels uses a dual RAG architecture for petition generation. RAG 1 retrieves case-specific factual evidence from classified document chunks. RAG 2 was partially implemented (`kb_chunks`, `kb_embeddings`, retrieval hooks, `kb_guidance_traces`) but not operationally integrated into generation.

The original RAG 2 design assumed strict section-key lookup — retrieve KB chunks where `document_type` matches allowed types per section. This approach risked collapsing useful rhetorical structure when successful petition sections did not map cleanly to the predefined taxonomy.

## Decision

RAG 2 is redesigned as **template-driven generation with section-aware preference**, not strict section-key filtering.

The retrievable object is an **abstracted rhetorical scaffold** — not raw KB prose. Extraction runs offline after KB document ingest. Retrieval at generation time uses **hybrid search**: section-key preference plus semantic similarity on template embeddings.

## Architecture

### Extraction phase (offline)

```
kb_chunk.text
  → LLM section detection + scaffold extraction
  → KBTemplate:
       - template_text (reusable scaffold with [EVIDENCE: ...] placeholders)
       - section_key (best taxonomy match or inferred label)
       - argument_sequence (rhetorical flow)
       - evidence_placeholders (expected insertion points)
       - confidence (mapping certainty)
       - embedding VECTOR(1536) (semantic retrieval vector)
```

### Retrieval phase (generation time)

```
current section_key + evidence_summary
  → semantic similarity search on kb_templates.embedding
  → top-N templates (section-aware preference, similarity fallback)
  → injected as drafting scaffold into generation prompt
```

### Constitutional separation

- **RAG 1** retrieves facts
- **RAG 2** retrieves reusable drafting structure
- **Generation** synthesizes both

## Storage

- New table: `kb_templates` (migration `0021`)
- New column: `embedding VECTOR(1536)` (migration `0022`, pending)

Raw `kb_chunk` text remains immutable. Templates are derived artifacts linked via `kb_chunk_id`. Re-extraction is possible when extraction prompts improve.

### Provenance

`kb_guidance_traces` currently stores `kb_chunk_id`.

Post-MVP: traces will be updated to reference `kb_template_id` to track which rhetorical template influenced each draft section.

For MVP, `kb_chunk_id` provenance is preserved as-is.

## Rules

- `template_text` is the source of truth, not `section_key`
- `section_key` is guidance metadata only
- Templates must remain retrievable even when taxonomy mapping is imperfect
- KB-derived templates are non-evidentiary, non-citable, structure-oriented only
- Client facts, names, dates, metrics, and achievements must never transfer from KB templates into generated petitions

## Out of Scope (Explicitly Post-MVP)

- Scaffold persistence systems
- Ontology frameworks
- Slot orchestration engines
- Cognition operating systems
- Scaffold versioning UI
- Evidence expectation infrastructure

## Current Implementation State

**Shipped (branch May26):**

- migration `0021`: `kb_templates` table
- `KBTemplate` SQLAlchemy model (`app/core/models.py`)
- `extract_kb_template` function (`app/kb/extractor.py`)

**Pending:**

- migration `0022`: `embedding VECTOR(1536)` on `kb_templates`
- embed step in `extractor.py`
- generation retrieval rewrite to use `kb_templates` vector search
- worker wiring for template extraction post-ingest

## Consequences

- Requires `embedding` column on `kb_templates` (migration `0022`)
- Requires updated extractor to embed `template_text` after LLM extraction
- Requires updated generation retrieval to use vector similarity on `kb_templates` instead of `document_type` filter on `kb_chunks`
- Existing `kb_guidance_traces` provenance model is preserved
