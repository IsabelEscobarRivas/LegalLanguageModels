ADR-009 — Acceptance Package
Status: Accepted
Accepted by: PM (ChatGPT)
Pending: PO (Isabel) formal sign-off
Gate: Sprint 5 does not open until PO accepts
The invariant is absolute and non-negotiable across all five phases:

No evidence, KB material, draft, trace, feedback, classification result, retrieval result, or citation_text may cross firm_id boundaries under any code path, query, or API call.

All Sprint 5 schema, query, and API work is subordinate to this invariant. If any Phase 2–5 deliverable cannot be built in compliance with ADR-009, it is blocked until the isolation guarantee is satisfied.

Sprint 5 Technical Specification
Phase 1 — Tenant Foundation
Task 1: Migration 0009 — Prompt templates into Alembic
File: alembic/versions/0009_prompt_templates_seed.py
Port all existing prompt template rows from the runtime seed script into a migration. Structure:

down_revision = "0008_background_affinity_fix"
Read existing templates from the script; insert via op.bulk_insert exactly as 0007/0008 do for reference data
After migration is applied, the runtime seed script is retired — Cursor deletes it or moves it to scripts/archive/
Add a comment in the migration header: # authoritative seed — runtime script retired

Validation: alembic upgrade head applies cleanly; SELECT COUNT(*) FROM prompt_templates matches the retired script's row count; no runtime script call needed on fresh container startup.

Task 2: firm_id schema propagation
File: alembic/versions/0010_firm_id_propagation.py
This migration does the following in order:
2a. Create firms table
sqlCREATE TABLE firms (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_firms_slug ON firms (slug);
2b. Seed a default firm for existing data
sqlINSERT INTO firms (id, name, slug)
VALUES ('<uuid>', 'Default Firm', 'default');
Store this UUID as a constant in the migration file — it will be referenced by the backfill step.
2c. Add firm_id to cases
sqlALTER TABLE cases ADD COLUMN firm_id VARCHAR(36) REFERENCES firms(id) ON DELETE RESTRICT;
UPDATE cases SET firm_id = '<default_firm_uuid>';
ALTER TABLE cases ALTER COLUMN firm_id SET NOT NULL;
CREATE INDEX ix_cases_firm_id ON cases (firm_id);
2d. Add firm_id to users
sqlALTER TABLE users ADD COLUMN firm_id VARCHAR(36) REFERENCES firms(id) ON DELETE RESTRICT;
UPDATE users SET firm_id = '<default_firm_uuid>';
ALTER TABLE users ALTER COLUMN firm_id SET NOT NULL;
CREATE INDEX ix_users_firm_id ON users (firm_id);
No changes to child tables (documents, chunks, classification_results, etc.) — they inherit firm scope through case_id. Their firm isolation is enforced at query time via join, not by adding redundant columns, unless query profiling in Sprint 6 shows a need.
SQLAlchemy models to update:

Case — add firm_id column and firm relationship
User — add firm_id column and firm relationship
New Firm model


Task 3: JWT claim propagation
File: app/core/auth.py
3a. Token generation — firm_id becomes a required field in the JWT payload:
python{
    "sub": user_id,
    "firm_id": firm_id,
    "role": role,
    "exp": expiry
}
3b. Token validation — middleware rejects any token missing firm_id. No route handler executes. HTTP 401 with body {"detail": "firm_id claim required"}.
3c. Dependency injection — current auth dependency returns user_id. Extend to return a TokenClaims dataclass:
python@dataclass
class TokenClaims:
    user_id: str
    firm_id: str
    role: str
All routes that currently receive user_id: str = Depends(get_current_user) are updated to receive claims: TokenClaims = Depends(get_current_user). Cursor does a project-wide find-and-replace on this signature — do not update routes one by one.
3d. Token generator script — scripts/generate_test_token.py updated to require --firm-id argument. Default firm UUID from migration 0010 used for QA token generation.

Task 4: Tenant boundary enforcement
File: app/core/database.py (or equivalent session factory)
Implement SQLAlchemy with_loader_criteria global filter on all models that carry firm_id directly (Case, User, Firm). The filter reads firm_id from a context variable set at request start by middleware.
Pattern:
pythonfrom contextvars import ContextVar

current_firm_id: ContextVar[str] = ContextVar("current_firm_id")

# Middleware sets it:
current_firm_id.set(claims.firm_id)

# Global filter applied to Session:
# Case.firm_id == current_firm_id.get()
# User.firm_id == current_firm_id.get()
All case-scoped queries through the ORM automatically inherit firm isolation. No route handler is trusted to apply firm_id manually.
Explicit predicate requirement: pgvector similarity queries in retrieval/ are raw SQL — they do not go through the ORM filter. These must be audited and updated manually to include cases.firm_id = :firm_id in the WHERE clause. Cursor produces a list of every raw SQL query in the codebase and confirms each one has been updated before Phase 1 is marked complete.
Phase 1 validation:

Generate two JWT tokens with different firm_id values
Create a case under firm A
Confirm firm B token cannot retrieve, classify, or generate against firm A's case
HTTP 404 (not 403) — firm B should not be able to confirm the case exists


Phase 2 — KB Persistence Layer
Migration 0011 — KB schema
File: alembic/versions/0011_kb_schema.py
sqlCREATE TABLE kb_documents (
    id VARCHAR(36) PRIMARY KEY,
    firm_id VARCHAR(36) NOT NULL REFERENCES firms(id) ON DELETE RESTRICT,
    title VARCHAR(500) NOT NULL,
    document_type VARCHAR(100) NOT NULL,  -- 'style_guide', 'firm_convention', 'precedent_letter'
    s3_key VARCHAR(1000) NOT NULL,
    lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'uploaded',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_kb_documents_firm_id ON kb_documents (firm_id);
CREATE INDEX ix_kb_documents_document_type ON kb_documents (document_type);

CREATE TABLE kb_chunks (
    id VARCHAR(36) PRIMARY KEY,
    firm_id VARCHAR(36) NOT NULL REFERENCES firms(id) ON DELETE RESTRICT,
    kb_document_id VARCHAR(36) NOT NULL REFERENCES kb_documents(id) ON DELETE RESTRICT,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    chunk_strategy VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_kb_chunks_firm_id ON kb_chunks (firm_id);
CREATE INDEX ix_kb_chunks_kb_document_id ON kb_chunks (kb_document_id);

CREATE TABLE kb_embeddings (
    id VARCHAR(36) PRIMARY KEY,
    firm_id VARCHAR(36) NOT NULL REFERENCES firms(id) ON DELETE RESTRICT,
    kb_chunk_id VARCHAR(36) NOT NULL REFERENCES kb_chunks(id) ON DELETE RESTRICT,
    embedding vector(1536) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_kb_embeddings_firm_id ON kb_embeddings (firm_id);
CREATE INDEX ix_kb_embeddings_kb_chunk_id ON kb_embeddings (kb_chunk_id);
CREATE INDEX ix_kb_embeddings_vector ON kb_embeddings 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
S3 prefix convention:
kb/{firm_id}/{document_type}/{kb_document_id}/{filename}
Firm ID is the first path component. No KB document for firm A can be stored under firm B's prefix. The ingestion service enforces this — it constructs the S3 key from claims.firm_id, never from a user-supplied path.
Endpoints:

POST /kb/documents — upload KB document, trigger chunk/embed pipeline
GET /kb/documents — list firm's KB documents (firm-scoped via global filter)
GET /kb/documents/{kb_document_id} — retrieve single document
POST /kb/documents/{kb_document_id}/search — semantic search within firm's KB

All endpoints require JWT with firm_id. Global ORM filter applies. No cross-firm query is possible.

Phase 3 — Taxonomy-Aware Hybrid Retrieval
Replaces the get_kb_style_guidance stub (ADR-007/008).
File: app/retrieval/kb_retrieval.py (new)
Two-stage retrieval per query:
Stage 1 — Symbolic filter
python# Filter kb_chunks by document_type matching the requested guidance category
# e.g. section_code='background' → document_type IN ('style_guide', 'firm_convention')
Stage 2 — Semantic ranking
python# pgvector cosine similarity on kb_embeddings
# WHERE firm_id = :firm_id  ← explicit, not ORM-filtered (raw SQL)
# ORDER BY embedding <=> :query_vec
# LIMIT :k
The symbolic filter runs first and narrows the candidate set. Semantic ranking runs second within that candidate set. This is the hybrid symbolic+semantic retrieval defined in ADR-008.
Firm isolation in raw SQL:
sqlSELECT kc.id, kc.text, ke.embedding <=> :query_vec AS distance
FROM kb_chunks kc
JOIN kb_embeddings ke ON ke.kb_chunk_id = kc.id
WHERE kc.firm_id = :firm_id
  AND kc.kb_document_id IN (
      SELECT id FROM kb_documents
      WHERE firm_id = :firm_id
        AND document_type = ANY(:allowed_types)
  )
ORDER BY distance
LIMIT :k
firm_id appears twice — on kb_chunks and in the subquery on kb_documents. Belt and suspenders. This is intentional.

Phase 4 — Controlled KB Injection
Core invariant (structural enforcement):
KB guidance and case evidence are written to separate trace tables and never merged.
New table — kb_guidance_traces (added to migration 0011 or 0012):
sqlCREATE TABLE kb_guidance_traces (
    id VARCHAR(36) PRIMARY KEY,
    draft_section_id VARCHAR(36) NOT NULL REFERENCES draft_sections(id) ON DELETE RESTRICT,
    kb_chunk_id VARCHAR(36) NOT NULL REFERENCES kb_chunks(id) ON DELETE RESTRICT,
    firm_id VARCHAR(36) NOT NULL REFERENCES firms(id) ON DELETE RESTRICT,
    guidance_type VARCHAR(50) NOT NULL,  -- 'style', 'rhetorical', 'convention'
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
generation_traces — unchanged. It retains its chunk_id and classification_result_id FKs. KB chunk IDs are never inserted into generation_traces.
draft_sections table — add one column:
sqlALTER TABLE draft_sections ADD COLUMN kb_guidance_applied BOOLEAN NOT NULL DEFAULT false;
Set to true when KB retrieval returns results that are injected into the generation prompt. Auditable without touching the evidence trace chain.
Prompt assembly contract:
[SYSTEM: section affinity rules + visa type context]
[EVIDENCE BLOCK: citation_text rows from generation_traces — immutable, case-scoped]
[KB GUIDANCE BLOCK: style/rhetorical guidance — firm-scoped, clearly delimited]
[USER: generate section]
The two blocks are structurally separated in the prompt. The LLM is instructed that evidence must be cited by source; KB guidance informs style only and must not be presented as case fact.

Phase 5 — Async Task Queue
Stack: ARQ over Redis
Task types:

ingest_document — extract → chunk → embed (case documents)
ingest_kb_document — extract → chunk → embed (KB documents)
classify_document_version — classify all chunks for a version
generate_draft — full generation pipeline for a case

Firm isolation in queue: every task payload carries firm_id extracted from the JWT at enqueue time. Workers validate firm_id on the payload against the resource being operated on before executing. A worker processing a task for firm A cannot operate on firm B's data even if firm B's resource ID appears in the payload.
Retry semantics:

Max retries: 3
Backoff: exponential, base 2s
Dead letter: failed tasks after 3 retries written to processing_events with status=failed and full error payload
No silent drops — every task either completes, retries, or writes a failure event

Redis key namespace: llm:{firm_id}:{task_type}:{task_id} — firm ID in the key prevents cross-firm queue inspection even at the Redis layer.

Sprint 5 — Sequencing invariant
Phase 1 must be complete and QA-validated before Phase 2 begins. KB infrastructure written before firm isolation is enforced is institutional memory with no tenant boundary — that is the failure mode the PM identified. Phase 2 through 5 execute in order with no phase beginning until the previous phase passes QA validation.
Ready to receive Sprint 5 backlog from PM. Phase 1 specs are Cursor-ready as written.
