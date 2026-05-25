# Sprint 2 Closeout — Trusted Retrieval Foundation

## Status

Sprint 2 completed with QA PASS.

24/25 checks passed.

Known limitation:

* cosine similarity retrieval currently lacks minimum similarity threshold, causing retrieval to always return top-k results.
* Logged for Sprint 3.

---

# Major Deliverables

Completed:

* JWT tenant isolation
* Chunking pipeline
* Embedding pipeline
* pgvector integration
* Retrieval endpoint with provenance
* Case-level events endpoint
* Event filtering
* Retrieval logging

---

# Architectural Decisions

## 1. Retrieval before classification

Decision:
Build retrieval/provenance substrate before legal classification workflows.

Rationale:
Classification quality depends on trustworthy chunking, embeddings, provenance, and tenant isolation.

---

## 2. Relational database remains operational source of truth

Decision:
Postgres remains the authoritative operational system.

Graph database discussion deferred.

Rationale:
Current system priorities are:

* transactional integrity
* auditability
* deterministic persistence
* workflow state management

---

## 3. Immutable operational history

Decision:
Operational records remain append-only where appropriate.

Rationale:
Legal systems require reproducibility and auditability.

---

# Known Limitations

## Retrieval thresholding

Current retrieval always returns top-k results.

Planned fix:
`min_similarity` threshold in Sprint 3.

---

# Concepts Learned

## Production Engineering Concepts

* state machines
* idempotency
* append-only events
* deterministic persistence
* transaction boundaries
* platform invariants
* tenant isolation
* provenance

## Infrastructure Concepts

* containerization
* orchestration
* object storage
* vector infrastructure

## Schema Evolution

Learned:

* databases evolve continuously during development
* Alembic enables controlled schema evolution
* migrations are part of architecture, not post-launch maintenance

---

# Sprint 3 Focus

Sprint 3 theme:
Classification + Human Review Foundation

Planned:

* multi-label classification
* immutable classification results
* classification feedback
* retrieval thresholding
* JWT protection for Sprint 1 endpoints

Deferred:

* generation
* async task queue
* orchestration layer
* graph database exploration

---

# PM Reflection

Major architectural insight:
Modern AI systems are operational systems first and AI systems second.

The system is evolving from:
document storage
→ retrieval
→ evidence interpretation
→ human-reviewed legal reasoning
→ future evidence-aware drafting.
