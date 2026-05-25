# ADR-002: Relational Database as Operational Source of Truth

**Status:** Accepted
**Date:** 2026-05-25

## Context

The system stores documents, versions, chunks, embeddings, processing events, retrieval logs, and will store classification results and generation traces. A choice was required: use a relational database (PostgreSQL) as the primary operational store, or distribute state across a relational store, a vector store, and a document store as separate systems of record.

The pressure came from the need for auditability. Legal platforms require the ability to answer: "What document produced this draft sentence? What chunk was retrieved? What version of that document was active at the time?" These are relational queries across append-only tables.

## Decision

PostgreSQL is the single operational source of truth for all structured state. pgvector extends PostgreSQL to handle vector similarity search. No external vector database (Pinecone, Weaviate, Qdrant) is introduced. No document store (MongoDB, Elasticsearch) is introduced. All foreign key relationships, audit trails, and provenance chains are enforced at the relational layer.

## Alternatives Considered

**Dedicated vector database (Pinecone).** Offload embedding storage and similarity search to a specialized vector store. Rejected because: introducing a second system of record creates provenance gaps — a chunk_id in Postgres must stay synchronized with a vector ID in Pinecone, and any drift breaks the audit trail. For a legal platform, broken provenance is a compliance risk.

**Document store for extracted text (MongoDB).** Store raw extracted text and chunk content in a document database, keep only metadata in Postgres. Rejected because: chunk text is referenced by classification results and generation traces — it must be in the same transactional boundary as those records to guarantee consistency.

**Event sourcing with separate read models.** Use an event store as the source of truth, project read models into Postgres. Rejected for Sprint 1-3 scope as overengineered — the append-only table pattern achieves the same auditability without the operational overhead of event sourcing infrastructure.

## Trade-Offs

**Gained:** Single transactional boundary for all provenance chains. Foreign keys enforce referential integrity across documents, versions, chunks, embeddings, and future classification results. No synchronization logic between systems. pgvector cosine similarity is available inside the same query that joins chunk metadata.

**Accepted:** pgvector will not match the query performance of dedicated vector databases at very large scale (millions of vectors). The accepted migration path: when vector query latency degrades measurably, extract embeddings to a dedicated vector store and maintain a synchronization layer. This migration is possible without breaking provenance because chunk_id remains the canonical reference.

## Consequences

All future services — classification, generation, evaluation — must write their outputs as rows in Postgres tables with foreign keys to the chunk and document version they reference. No service is permitted to maintain its own private state store. The `alembic` migration chain is the authoritative schema history.

## Invariants Introduced

- PostgreSQL is the single operational source of truth
- All AI outputs are rows in Postgres with FK provenance to source chunks
- No external data store is introduced without an explicit ADR superseding this one
- `alembic upgrade head` is the only permitted schema migration mechanism
- `Base.metadata.create_all` is never used in production code paths

## Related Components

`app/core/database.py`, `app/core/models.py`, all Alembic migrations, `docker-compose.yml` (pgvector image), all future classification and generation models
