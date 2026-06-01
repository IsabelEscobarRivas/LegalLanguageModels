Noted and elevated. This is correct — provenance visibility is not a UI nicety, it's a constitutional requirement. An attorney who cannot answer "how did this document participate in the final draft?" cannot meaningfully review the output.

Recording this as a formal Sprint 7.6 architectural requirement:

---

**ADR-013 (proposed): Document Provenance Visibility**

The platform must expose document participation provenance directly in the attorney UI without requiring raw trace inspection. This is an extension of ADR-004 (Provenance-first legal AI) into the human review layer.

**Core user question the UI must answer:**
> "How did this document participate in the final draft?"

**Terminology change — permanent:**
- `chunks` → **Evidence Excerpts** in all user-facing displays
- This applies to UI labels, API response field names surfaced to users, and all future documentation

**Two-level document view:**

*Document Row* — quick operational overview:
filename, lifecycle badge, participation state badge, extraction method, retrieval/generation eligible flags, evidence excerpt count, classification count, draft section contribution summary

*Document Detail* — full provenance:
extraction diagnostics, extraction confidence, text density, integrity status, all evidence excerpts with classification, coverage contribution per criterion, draft section participation, processing event timeline, exclusion reasons if any

**Draft section contribution display:**
```
Contributed to: Background · Experience · Impact
```
or:
```
No draft participation
Reason: ingestion_failed
```

---

This goes into the Sprint 7.6 spec as Package 1 before any other UI work. It's the foundational view that makes everything else reviewable.
