# Sprint 4 — Provenance-Aware Legal Draft Generation

## Objective

Generate evidence-backed, section-oriented legal draft content for EB-1 and EB-2 NIW immigration petitions. Every generated sentence traces to a specific chunk, classification result, and citation.

## Architecture Specs

- [S4-A01 — Generation Architecture](S4-A01-generation-architecture-spec.md)
- [S4-A02 — Prompt Template Architecture](S4-A02-prompt-template-architecture.md)

## Legal Mapping

- [EB-2 NIW Evidence Mapping](S4-mapping-eb2-niw.md)
- [EB-1 Evidence Mapping](S4-mapping-eb1.md)

## Prompt Templates

- [EB-1 Prompt Templates](S4-eb1-prompt-templates.md)
- EB-2 NIW templates are in S4-A02

## Implementation Tickets

| Ticket | Title | Status |
|--------|-------|--------|
| S4-D01 | citation_text and routing reference schema | Pending |
| S4-D02 | Paragraph chunking strategy | Pending |
| S4-D03 | Updated classification for citation_text | Pending |
| S4-D04 | Visa-type-aware section routing | Pending |
| S4-D05 | Prompt template persistence | Pending |
| S4-D06 | Generation trace persistence | Pending |
| S4-D07 | Coverage gate enforcement | Pending |
| S4-D08 | Section-based draft generation service | Pending |
| S4-D09 | Draft output schema | Pending |
| S4-D10 | Draft retrieval APIs | Pending |
| S4-D11 | .txt extraction support | Pending |

## Key Invariants

- Generation never runs without a complete provenance chain
- citation_text is the atomic citation unit — never the full chunk
- conclusion section is always generated from coverage summary — never from retrieved evidence
- Coverage gate is enforced before generation — incomplete coverage returns 422 not silent gaps
- Draft outputs are immutable — append-only
- Prompt templates are versioned and append-only — no updates, only new versions
