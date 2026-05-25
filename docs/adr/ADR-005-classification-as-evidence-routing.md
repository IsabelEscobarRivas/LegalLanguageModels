# ADR-005: Classification as Evidence Routing for Narrative Generation

**Status:** Accepted
**Date:** 2026-05-25

## Context

The platform's end goal is AI-assisted drafting of immigration petition letters. These letters have a defined structure: background, experience, expert opinion, achievements, impact, conclusion. Evidence from uploaded documents must be routed to the correct section. A choice was required about what role classification plays: is it legal labeling (tagging documents with USCIS criteria) or is it routing logic (directing evidence to narrative sections)?

The pressure comes from the gap between what USCIS criteria describe and what petition letter sections require. A chunk classified as supporting "NIW Criterion 2: Positioned to Advance the Field" might belong in the experience section, the achievements section, or the expert_opinion section depending on its content. Criterion classification alone is insufficient for narrative routing.

## Decision

Classification operates on two axes simultaneously: legal criteria mapping (which USCIS criterion does this chunk support?) and section affinity mapping (which narrative section does this chunk belong in?). Both are stored as fields on `classification_results`. Generation in Sprint 4 uses section affinity — not legal criteria — as the primary routing signal for assembling draft sections. Legal criteria are used for compliance checking, not for narrative assembly.

## Alternatives Considered

**Criteria-only classification.** Classify chunks by USCIS criterion only, let the generation model decide which section to use the evidence in. Rejected because: the generation model has no reliable way to infer section affinity from criteria alone without additional context, and allowing the model to make this routing decision without explicit supervision introduces unauditable behavior into a legally sensitive output.

**Section-only classification.** Classify chunks by target section only, ignore USCIS criteria. Rejected because: legal compliance requires knowing which criterion each piece of evidence supports. A petition that uses strong evidence in the wrong section fails on criteria coverage even if the narrative is well-written.

**No classification, full RAG.** Retrieve relevant chunks for each section prompt, let the LLM decide what to include. Rejected because: without classification, the system cannot guarantee that all required USCIS criteria are covered by at least one piece of evidence. Coverage gaps in a petition are a compliance failure.

## Trade-Offs

**Gained:** Section affinity classification makes narrative assembly deterministic and auditable. Legal criteria classification makes compliance coverage verifiable. The two axes together enable automated coverage gap detection before draft generation begins.

**Accepted:** Dual-axis classification is more complex to implement and validate than single-axis. The `classification_results` schema must carry both `criteria_id` and `section_affinity` as independent fields. Human reviewers must understand both axes when providing feedback. Classification prompts must be carefully designed to elicit both axes reliably from the LLM.

## Consequences

Sprint 3 must produce a `classification_results` schema with both `criteria_id` (FK to a criteria reference table) and `section_affinity` (enum or FK) as required fields. Generation in Sprint 4 queries `classification_results` grouped by `section_affinity` to assemble each section of the petition letter. A coverage check before generation must verify that every required USCIS criterion has at least one classified chunk supporting it. If coverage is incomplete, generation must surface a warning rather than produce a draft with gaps.

## Invariants Introduced

- Classification always produces both a legal criteria mapping and a section affinity mapping
- Section affinity is the primary routing signal for narrative generation
- Legal criteria coverage is verified before draft generation begins
- A draft is never generated for a case with incomplete criteria coverage without an explicit human override

## Related Components

`classification_results` (Sprint 3), criteria reference table (Sprint 3), `section_affinity` enum (Sprint 3), `generation_traces` (Sprint 4), `draft_outputs` (Sprint 4), `app/retrieval/router.py` (provenance chain that classification extends)
