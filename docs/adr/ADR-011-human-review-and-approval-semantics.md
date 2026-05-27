# ADR-011: Human Review and Approval Semantics

**Status:** Proposed
**Date:** 2026-05-27
**Authors:** Architect (Claude)
**Related:** ADR-004 (Provenance-first), ADR-009 (Tenant isolation), ADR-010 (KB operationalization)

---

## Context

Sprint 6 closed with a platform capable of generating provenance-traced, KB-conditioned legal draft sections. The evidence chain from source document to generated text is structurally enforced and QA-verified. The platform now needs a human review layer — the mechanism by which a licensed attorney validates, corrects, or approves generated content before it becomes a legal submission artifact.

This ADR defines the semantics of that review layer: what reviewers can do, what they cannot do, how their actions interact with provenance integrity, and what the export artifact represents.

---

## Problem Statement

Human review introduces three risks that must be governed:

**Risk 1 — Edit corruption.** If an attorney edits generated content and the system treats the edited version as having the same provenance as the generated version, the audit trail is false. A sentence added by the attorney would appear to be evidence-bound when it is not.

**Risk 2 — Approval ambiguity.** Without explicit approval semantics, it is unclear whether a draft was reviewed at all, partially reviewed, or fully approved. A USCIS submission requires a clear attestation that the document was reviewed by a licensed attorney.

**Risk 3 — Regeneration provenance drift.** If a section is regenerated after initial review, the new generation may have different evidence than the original. The review history must record which version was approved, not just that approval occurred.

---

## Architectural Decisions

### Decision 1: Reviews are append-only rows, never mutations

Reviewer actions create new `DraftSectionReview` rows. They never modify `draft_sections`, `generation_traces`, or `kb_guidance_traces`. If an attorney edits a section, the edit is stored as a `reviewer_edit` field on the review row, not as an update to `draft_sections.content`.

**Rationale:** Mutating `draft_sections` would corrupt the evidence audit trail. The generated content is the provenance-traced artifact. Attorney edits are a separate layer of human judgment applied on top of it.

### Decision 2: Three reviewer actions — approve, reject, edit

- **approve:** Reviewer attests the section as generated is accurate and suitable for submission.
- **reject:** Reviewer flags the section as unsuitable. Triggers regeneration eligibility.
- **edit:** Reviewer provides a corrected version. The edit is stored separately from generated content. The export uses the edited version but the provenance record shows both the generated original and the reviewer edit.

### Decision 3: Regeneration creates a new DraftSection row

When a rejected section is regenerated, a new `DraftSection` row is created with a new `draft_output_id`-level linkage. The old section row is never modified. The review history links the original section, the rejection reason, and the new section ID.

### Decision 4: Export snapshots are immutable

`DraftExport` rows record the exact content exported — including which section version (generated or edited) was used — at the moment of export. Exports are append-only. A re-export creates a new row. The export artifact is the legal document of record.

### Decision 5: Reviewer authority is bounded

Reviewers may approve, reject, or edit individual sections. They may not modify `generation_traces`, `classification_results`, or `kb_guidance_traces`. They may not alter the evidence provenance chain. Their edits are clearly marked in the export as attorney-reviewed content distinct from AI-generated content.

---

## Schema

### `draft_section_reviews` table

```sql
CREATE TABLE draft_section_reviews (
    id VARCHAR(36) PRIMARY KEY,
    draft_section_id VARCHAR(36) NOT NULL REFERENCES draft_sections(id) ON DELETE RESTRICT,
    case_id VARCHAR(36) NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    firm_id VARCHAR(36) NOT NULL REFERENCES firms(id) ON DELETE RESTRICT,
    reviewer_id VARCHAR(255) NOT NULL,
    action VARCHAR(30) NOT NULL,
        -- CHECK: action IN ('approved', 'rejected', 'edited')
    reviewer_edit TEXT,
        -- NULL when action = 'approved' or 'rejected'
        -- Contains attorney's corrected text when action = 'edited'
    rejection_reason TEXT,
        -- NULL when action != 'rejected'
    regeneration_requested BOOLEAN NOT NULL DEFAULT false,
    regenerated_section_id VARCHAR(36) REFERENCES draft_sections(id),
        -- Set after regeneration completes
    created_at TIMESTAMP NOT NULL DEFAULT now()
    -- append-only: no updated_at
);
```

### `draft_exports` table

```sql
CREATE TABLE draft_exports (
    id VARCHAR(36) PRIMARY KEY,
    draft_output_id VARCHAR(36) NOT NULL REFERENCES draft_outputs(id) ON DELETE RESTRICT,
    case_id VARCHAR(36) NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
    firm_id VARCHAR(36) NOT NULL REFERENCES firms(id) ON DELETE RESTRICT,
    exported_by VARCHAR(255) NOT NULL,
    export_format VARCHAR(30) NOT NULL,
        -- CHECK: export_format IN ('json', 'txt', 'pdf')
    section_snapshot JSONB NOT NULL,
        -- Full content of each section at export time
        -- Including which version (generated vs edited) was used
    review_snapshot JSONB NOT NULL,
        -- Review state of each section at export time
    s3_export_key VARCHAR(1000),
        -- S3 key of the exported file if stored
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

---

## Provenance Implications of Reviewer Actions

| Action | Generated content | Provenance trace | Export content |
|---|---|---|---|
| approve | Unchanged | Unchanged | Generated content |
| reject | Unchanged | Unchanged | Section excluded or sentinel |
| edit | Unchanged | Unchanged + review row | Attorney edit (labeled) |
| regenerate | New DraftSection | New traces for new section | New generated content |

The generated content and its provenance traces are never modified by reviewer actions. They are the immutable record of what the AI produced and why.

---

## Export Governance

An export is permitted when:
- All sections have a review row with `action IN ('approved', 'edited')`
- No section has `action = 'rejected'` without a `regenerated_section_id`

The export artifact labels each section with its provenance type:
- `AI_GENERATED` — approved as generated
- `ATTORNEY_EDITED` — approved with edits
- `REGENERATED` — original rejected, regeneration approved

---

## Auditability Guarantees

- Every reviewer action is persisted with `reviewer_id`, `action`, and `created_at`
- The full review history for a section is recoverable from `draft_section_reviews`
- The export snapshot records the exact content exported — not a pointer to current content
- Re-exports create new rows — prior exports are never overwritten
