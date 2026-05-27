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
