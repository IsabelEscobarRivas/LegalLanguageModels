# ADR-001: Retrieval Before Classification

**Status:** Accepted
**Date:** 2026-05-25

## Context

The platform targets multi-document evidence synthesis for legal drafting. Two sequencing strategies were available at Sprint 1: build classification first (label documents on ingest, then retrieve by label) or build retrieval first (embed and retrieve semantically, then classify retrieved evidence). The team had to commit to one sequence because each imposes different schema dependencies and different ordering of engineering work.

The pressure to sequence came from a real constraint: classification schema depends on knowing what you are classifying against (USCIS criteria, section affinity targets), while retrieval schema depends only on the document content itself. These are asymmetric dependencies.

## Decision

Retrieval infrastructure is built before classification infrastructure. Chunking, embedding, and vector search are production-ready before any classification logic is written. Classification in Sprint 3 will operate on already-retrieved chunks, not on raw documents.

## Alternatives Considered

**Classification first.** Label documents at ingest time using rule-based or LLM-based classifiers, then retrieve only documents matching a given label. Rejected because: classification criteria (USCIS EB1/EB2 NIW criteria, section affinity targets) are domain-specific and evolve; hard-coding them before retrieval means every criterion change requires re-ingestion. Retrieval is more stable.

**Simultaneous build.** Build retrieval and classification in parallel in the same sprint. Rejected because: the two subsystems share the chunk as a fundamental unit, and the chunk schema must be stable before classification can reference it. Parallel build would have produced two unstable schemas competing for the same data model.

**RAG-only architecture (no classification).** Retrieve and generate directly without classification. Rejected because: for legal drafting, unclassified evidence cannot be reliably routed to the correct section of a petition letter. A claim about salary history must go to a different section than a claim about peer recognition. Classification is the routing mechanism.

## Trade-Offs

**Gained:** Retrieval infrastructure is stable and independently testable before classification complexity is introduced. Chunk provenance is established before classification references it. Re-classification does not require re-embedding.

**Accepted:** Sprint 2 cannot produce legally meaningful outputs — retrieval returns semantically similar chunks but does not know which USCIS criterion they support. The system is technically correct but legally incomplete until Sprint 3.

## Consequences

Classification in Sprint 3 must reference `chunk_id` and `document_version_id` — both now exist and are stable. Generation in Sprint 4 can rely on classified, retrieved chunks with full provenance. The sequence `retrieval → classification → generation` is now the canonical pipeline order and cannot be reversed without schema migrations.

## Invariants Introduced

- Classification is never built before a stable retrieval layer exists
- Classification operates on chunks, not on raw documents
- Re-classification does not trigger re-embedding

## Related Components

`chunks`, `embeddings`, `retrieval_logs`, `app/ingestion/chunker.py`, `app/ingestion/embedder.py`, `app/retrieval/router.py`, Sprint 3 classification service (pending)
