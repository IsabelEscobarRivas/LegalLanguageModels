# MVP Acceptance Criteria Document

**Document type:** MVP closure gate
**Status:** Active
**Acceptance authority:** PO (Isabel)

---

## Operational Requirements

- [ ] A case can be created and documents uploaded via the UI without database access
- [ ] Documents progress through the full lifecycle (`received → ingested → chunked → embedded → indexed`) with visible status in the UI
- [ ] KB documents can be uploaded and ingested to `indexed` state via the UI
- [ ] Draft generation can be triggered from the UI
- [ ] Generation completes within 5 minutes for a case with 10 documents
- [ ] The platform recovers from a container restart without data loss
- [ ] Dead-letter ARQ tasks are visible and retrievable

## Reviewer Workflow Requirements

- [ ] An attorney can review each draft section individually
- [ ] An attorney can approve, reject, or edit each section
- [ ] An attorney can trigger regeneration of a rejected section
- [ ] The review state of each section is visible in the UI
- [ ] A draft cannot be exported until all sections are approved or edited
- [ ] Review history is persisted and retrievable

## Provenance Inspection Requirements

- [ ] An attorney can click any sentence in a generated section and see the source citation
- [ ] The source document name is visible for every citation
- [ ] KB guidance is visually distinguished from evidence citations
- [ ] The provenance invariant query returns 0 after every generation run
- [ ] `GET /kb/invariants` returns all checks `status: ok` at any time

## Export Guarantees

- [ ] Export produces an immutable snapshot of section content at export time
- [ ] Export labels each section as `AI_GENERATED`, `ATTORNEY_EDITED`, or `REGENERATED`
- [ ] Export history is retrievable
- [ ] Re-export creates a new record, prior exports unchanged

## Observability Guarantees

- [ ] Failed lifecycle states are detectable via API without database access
- [ ] Async queue health is visible
- [ ] Generation lineage (which evidence produced which section) is queryable
- [ ] KB pipeline events are visible per document

## Auditability Guarantees

- [ ] Every reviewer action is persisted with reviewer identity and timestamp
- [ ] The export record includes the review state at time of export
- [ ] Classification feedback is traceable to the reviewer who submitted it

## Recovery Guarantees

- [ ] A stuck ARQ task can be identified and re-enqueued without data corruption
- [ ] A partial generation (some sections generated, some failed) can be resumed
- [ ] A failed KB ingestion can be re-triggered after root cause is fixed

## Invariants That Must Hold at MVP Closure

```sql
-- Provenance separation — must always return 0
SELECT COUNT(*) FROM generation_traces gt
JOIN kb_chunks kc ON kc.id = gt.chunk_id;

-- No orphaned generation traces
SELECT COUNT(*) FROM generation_traces gt
WHERE NOT EXISTS (
    SELECT 1 FROM draft_sections ds WHERE ds.id = gt.draft_section_id
);

-- No orphaned KB guidance traces
SELECT COUNT(*) FROM kb_guidance_traces kgt
WHERE NOT EXISTS (
    SELECT 1 FROM draft_sections ds WHERE ds.id = kgt.draft_section_id
);

-- All exports have review snapshots
SELECT COUNT(*) FROM draft_exports WHERE review_snapshot IS NULL;
-- Must return 0
```

## Explicit Non-Goals

The following are explicitly out of scope for MVP:

- Multi-user collaboration on the same draft
- Role-based access control beyond attorney/admin
- Billing or usage tracking
- Automated quality scoring of sections
- Autonomous re-generation without attorney trigger
- Enterprise admin dashboard
- Multi-language support
- Mobile-optimized UI
- SLA monitoring
- Integration with case management systems

## User 0 Validation Criteria

MVP is complete when a trusted legal professional — without architect or developer assistance — can:

1. Log in with a firm JWT
2. Create a case and upload evidence documents
3. Upload a KB style guide
4. Trigger chunking, embedding, and classification
5. Trigger draft generation
6. Review each section: approve, edit, or reject and regenerate
7. Inspect the provenance of at least one citation
8. Confirm KB guidance is visually separate from evidence
9. Export the final approved draft
10. Retrieve the export history

All steps must complete without errors. Provenance invariant must hold throughout.
