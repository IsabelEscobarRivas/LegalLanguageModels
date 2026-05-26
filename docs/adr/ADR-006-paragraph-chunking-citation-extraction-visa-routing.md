# ADR-006: Paragraph-Level Chunking, Citation Extraction, and Visa-Type-Aware Section Affinity Routing

**Status:** Accepted
**Date:** 2026-05-26
**Supersedes:** N/A
**Superseded by:** N/A

## Context

Sprint 3 implemented fixed-size chunking (512 characters, 50 character overlap) and dual-axis classification (USCIS criteria + section affinity). This worked correctly for general document content. However, review of real EB-1 and EB-2 NIW petition letters revealed three structural patterns that the current architecture cannot handle correctly:

Pattern 1 — Petition letters are paragraph-structured, not character-structured. An EB-1 petition letter has explicit sections: "Evidence of membership in associations..." followed by paragraphs arguing that criterion. An EB-2 NIW letter argues three Dhanasar prongs holistically across the entire document. Fixed-size chunking cuts across paragraph boundaries, destroying the semantic unit that the classifier needs to evaluate. A 512-character window that begins mid-paragraph and ends mid-sentence provides the LLM with degraded context, producing lower confidence scores and more misclassifications than a window that respects paragraph boundaries.

Pattern 2 — Classification produces criterion-to-chunk mapping but not citation-level evidence. The current classification_results schema records which chunk supports which criterion, but not which specific sentence within the chunk is the actual evidence. For legal drafting, this is insufficient. A generated draft sentence asserting "Dr. Enjiu has demonstrated extraordinary ability as a judge of others' work" must cite the specific passage — "his participation as an effective member of the judging committee for the Specialization Course in Orthodontics at FACULDADE DO CENTRO OESTE PAULISTA" — not just "chunk 4 of document version 1." Citation-level provenance is the minimum granularity for legal defensibility.

Pattern 3 — EB-1 and EB-2 NIW have structurally different evidence patterns requiring different section affinity routing. EB-1 criteria A-J are argued in isolated sections of the petition letter — each criterion has its own evidentiary section with specific supporting paragraphs. EB-2 NIW criteria C1-C3 are argued holistically — a single expert opinion paragraph may simultaneously support C1 (substantial merit), C2 (well-positioned), and C3 (national interest waiver). The section affinity routing logic for EB-1 must map criteria to specific letter sections differently than EB-2 NIW routing, which distributes evidence across sections based on rhetorical function rather than regulatory category.

## Decision

Three decisions are locked by this ADR:

Decision 1: Paragraph-level chunking is introduced as a first-class chunking strategy alongside fixed-size chunking. The chunk_strategy field on the chunks table already exists and accepts any string value. The new value paragraph is added. Paragraph chunking splits document text at double-newline boundaries (\n\n) and paragraph markers, preserving semantic units. Minimum paragraph size: 50 characters (merge short paragraphs into the preceding one). Maximum paragraph size: 2000 characters (split oversized paragraphs at sentence boundaries). chunk_strategy_version is incremented to 2.0 for paragraph chunking. The chunking pipeline is extended with a strategy parameter — existing fixed_size behavior is unchanged. Petition letters are processed with paragraph strategy by default; other documents retain fixed_size.

Decision 2: A citation_text field is added to classification_results. This field contains the specific sentence or phrase extracted by the LLM as the primary evidence for the classification. The LLM classifier prompt is updated to elicit a fifth output field alongside supports, confidence, rationale, and section_affinity. The field is nullable — if the LLM cannot identify a specific citation, it is stored as null and the full chunk text serves as the citation in generation. citation_text is the atomic unit of legal provenance in generated drafts.

Decision 3: Section affinity routing is visa-type-aware. EB-1 uses criteria-to-section mapping: criteria A-B-C-D map primarily to achievements and expert_opinion; criteria E-F map to achievements; criterion H maps to experience; criterion I maps to impact; criteria G-J map to achievements. EB-2 NIW uses prong-to-section mapping: C1 (substantial merit) maps primarily to impact; C2 (well-positioned) maps primarily to experience and achievements; C3 (national interest waiver) maps to impact and conclusion. These mappings are stored as configurable seed data in a new criteria_section_affinity_defaults reference table, not hardcoded in application logic. The LLM classifier retains authority to override the default mapping based on chunk content — the default is a prior, not a constraint.

## Alternatives Considered

**Fixed-size chunking only.** Keep 512-character fixed chunks for all document types. Rejected because: petition letter paragraphs are the atomic legal argument unit. A paragraph arguing that an applicant "has been recognized internationally" is a complete legal claim. Splitting it mid-sentence produces fragments that the classifier cannot evaluate with full context, reducing classification accuracy on the documents that matter most.

**Semantic chunking via embedding similarity.** Use embedding distance to find natural topic boundaries. Rejected for Sprint 4 because: semantic chunking requires an additional embedding pass before the chunking step, adding latency and cost. Paragraph boundaries in legal documents are already semantic boundaries — attorneys write petition letters in structured paragraphs by convention. Paragraph chunking achieves semantic coherence without the additional complexity.

**Citation extraction via post-processing.** Classify first, then run a second LLM pass to extract citations from classified chunks. Rejected because: the classifier already reads the full chunk text to make its classification decision. Extracting the citation in the same call is zero additional cost and preserves the exact reasoning context. A second pass would re-read the chunk without the classification context and produce lower quality citations.

**Single section affinity mapping for all visa types.** Use one universal mapping from criteria to sections regardless of visa type. Rejected because: EB-1 criterion H (critical role) maps to experience, but EB-2 NIW C2 (well-positioned) also maps to experience — yet the evidence for each is structurally different. An expert opinion letter supporting EB-1 Criterion D (judging others' work) maps to expert_opinion, but the same letter supporting EB-2 NIW C2 maps to experience. The mapping must be visa-type-aware or section routing produces incorrect draft assembly.

## Trade-Offs

**Gained:** Paragraph-level chunking preserves the legal argument unit, improving classifier accuracy on petition letters. Citation-level provenance enables attorneys to verify every generated claim against a specific source passage. Visa-type-aware routing produces correctly structured draft sections for both EB-1 and EB-2 NIW petitions. The criteria_section_affinity_defaults table enables routing updates without code changes.

**Accepted:** Paragraph chunking produces variable-length chunks — some paragraphs are 80 characters, some are 1800. This makes embedding comparison across chunks less uniform than fixed-size chunking. The tradeoff is accepted: legal correctness of the semantic unit matters more than embedding uniformity. Citation extraction adds one output field to every LLM classification call — if the model returns a malformed response, the fallback is null citation and full chunk text. The criteria_section_affinity_defaults table adds a new reference table to the schema and a new Alembic migration.

## Consequences

The following changes are required in Sprint 4:

- Alembic migration adding citation_text TEXT NULL to classification_results
- Alembic migration creating criteria_section_affinity_defaults reference table with seed data for EB-1 and EB-2 NIW
- app/ingestion/chunker.py extended with paragraph strategy — existing fixed_size unchanged
- app/classification/classifier.py prompt updated to elicit citation_text — existing classification_results rows have citation_text = NULL, which is valid
- app/classification/classifier.py section affinity resolution updated to consult criteria_section_affinity_defaults as prior before accepting LLM override
- Generation in Sprint 4 assembles draft citations from classification_results.citation_text when non-null, falling back to chunks.text when null
- QA must verify that citation_text is populated on classifications produced after this ADR is implemented

All Sprint 3 classification_results rows with citation_text = NULL remain valid. The column is nullable by design — null means "full chunk is the citation." No backfill is required.

## Invariants Introduced

- citation_text is the atomic citation unit for generated draft sentences — never the full document
- Paragraph chunking is the default strategy for petition letters — fixed-size is the default for all other document types
- Section affinity routing consults criteria_section_affinity_defaults as a prior — LLM may override but must justify in rationale
- chunk_strategy on every Chunk row is the authoritative record of how that chunk was produced — generation never assumes a chunking strategy

## Related Components

`chunks` table (chunk_strategy, chunk_strategy_version), `classification_results` table (new citation_text column), `criteria_section_affinity_defaults` (new reference table), `app/ingestion/chunker.py`, `app/classification/classifier.py`, `app/classification/router.py`, Sprint 4 generation service (pending), `docs/adr/README.md` (index update needed)
