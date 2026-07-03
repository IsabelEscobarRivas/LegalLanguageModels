# LegalLanguageModels V2

An AI-powered legal document processing platform for immigration case management. LegalLanguageModels automates document analysis, evidence retrieval, classification, and legal narrative generation with full provenance tracking and attorney review workflows.

---

## Overview

LegalLanguageModels V2 is a production-grade system for:

- **Document Ingestion** — Upload case documents; extract and chunk text automatically
- **Evidence Retrieval** — Retrieve case evidence and knowledge base guidance with source citations
- **Legal Classification** — Classify documents by USCIS criteria and section affinity with immutable audit trails
- **Narrative Generation** — Generate legal petition narratives grounded in evidence with provenance
- **Attorney Review** — Human-in-the-loop review, editing, and approval workflows
- **Export & Audit** — Export frozen drafts with full review history and compliance guarantees

Key architectural principles:

- **Provenance-first**: Every AI output is traced to source documents
- **Immutable by design**: Classification and generation results are append-only
- **Tenant-isolated**: JWT-enforced per-case boundaries with PostgreSQL multi-tenancy
- **Operational**: Relational database + vector store + async task queue for production reliability

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **API Framework** | FastAPI 0.109.2 |
| **Database** | PostgreSQL 13 (pgvector for embeddings) |
| **Task Queue** | ARQ (Redis-backed) |
| **Authentication** | JWT |
| **Vector Embeddings** | OpenAI embeddings (1536-dim) + pgvector storage |
| **LLM Models** | GPT-4o (generation + classification) |
| **Document Processing** | PyPDF2, pytesseract, python-docx, Pillow |
| **Semantic Search** | Sentence-transformers, scikit-learn, spacy |
| **Infrastructure** | Docker Compose (local) + Railway (production) |
| **Schema Versioning** | Alembic |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.9+
- AWS credentials (S3 bucket for document storage)
- OpenAI API key

### Setup

1. **Clone and environment setup:**

```bash
git clone https://github.com/IsabelEscobarRivas/LegalLanguageModels.git
cd LegalLanguageModels
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment variables:**

```bash
cp .env.example .env
```

Fill in:
- `DATABASE_URL` — PostgreSQL connection string (Supabase or local)
- `REDIS_URL` — Redis connection (local or hosted)
- `AWS_ACCESS_KEY` — AWS credentials for S3
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME` — S3 bucket for document storage
- `OPENAI_API_KEY` — OpenAI API key
- `JWT_SECRET` — Secret for JWT signing

3. **Start the stack:**

```bash
docker-compose up -d
```

This runs:
- **Web service** (FastAPI): `http://localhost:8000`
- **Worker service** (ARQ): async task processing
- **PostgreSQL** (pgvector): relational + vector data
- **Redis**: task queue + caching

4. **Health check:**

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "database": "ok",
  "s3": "ok"
}
```

5. **Interactive API docs:**

Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

---

## Core API Endpoints

### Cases

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/cases` | POST | Create a new case |
| `/cases` | GET | List all cases for firm |
| `/cases/{case_id}/documents` | GET | List case documents with status |

### Documents

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/documents` | POST | Upload document to case |
| `/documents/{doc_id}/versions` | GET | List document versions |

### Knowledge Base

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/kb/documents` | POST | Upload KB reference document |
| `/kb/documents/{id}/ingest` | POST | Ingest KB document (chunk → embed → index) |
| `/kb/invariants` | GET | Verify KB system integrity |

### Retrieval (RAG)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/retrieval/search` | POST | Retrieve evidence + KB guidance with citations |

### Classification

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/classification/classify` | POST | Classify document by criteria + section affinity |

### Generation

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/generation/generate` | POST | Generate legal narrative with provenance |

### Review

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/review/sections` | GET | List draft sections for review |
| `/review/sections/{id}/approve` | POST | Approve draft section |
| `/review/sections/{id}/reject` | POST | Reject with regeneration request |

### Export

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/generation/drafts/{id}/export` | POST | Export frozen draft with review history |

---

## Document Lifecycle

Documents flow through a deterministic state machine:

```
uploaded → extracted → chunked → embedded → indexed
             ↓           ↓         ↓
            (failure recovery paths)
```

Each stage is **idempotent**:
- Calling the same stage twice on completed work is safe (skips processing)
- ARQ retries are transparent to the caller
- Partial failures can be resumed without data corruption

---

## Architecture Highlights

### Provenance-First Design

Every chunk retrieved, every classification made, every sentence generated is traced back to source documents:

- **Retrieval traces**: map retrieved chunks → source document + offset
- **Generation traces**: map generated text → evidence chunks used
- **Classification provenance**: link classification → evidence reasoning
- **Invariant enforcement**: queries verify `generation_traces` never reference KB-only chunks

### Multi-Tenancy & Isolation

- JWT contains `firm_id` (tenant identifier)
- Database queries filtered by `firm_id` at API layer
- Case-level isolation: users can only see cases for their firm
- Token validation on every protected endpoint

### Immutable Audit Trail

- Classification results are append-only (no UPDATE/DELETE)
- Generation results are immutable (attorney edits create new records)
- Review actions tracked with reviewer identity + timestamp
- Export creates frozen snapshot at export time

### Async Task Processing

ARQ-based task queue for long-running work:

- Document ingestion (chunking → embedding → indexing)
- KB document processing
- Classification batch runs
- Generation with LLM calls

Task retries with exponential backoff; failed tasks logged in dead-letter queue.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✓ | — | PostgreSQL connection string |
| `REDIS_URL` | ✓ | — | Redis connection for task queue |
| `AWS_ACCESS_KEY` | ✓ | — | AWS access key for S3 |
| `AWS_SECRET_ACCESS_KEY` | ✓ | — | AWS secret key for S3 |
| `S3_BUCKET_NAME` | ✓ | — | S3 bucket name for documents |
| `OPENAI_API_KEY` | ✓ | — | OpenAI API key (GPT-4o) |
| `JWT_SECRET` | ✓ | — | Secret for JWT signing/verification |
| `AWS_REGION` | | us-east-2 | AWS region for S3 |
| `GENERATION_MODEL` | | gpt-4o | LLM model for generation |
| `CLASSIFICATION_MODEL` | | gpt-4o | LLM model for classification |
| `EMBEDDING_DIMENSIONS` | | 1536 | OpenAI embedding dimension |
| `CHUNK_SIZE` | | 512 | Characters per chunk (max) |
| `PARAGRAPH_MAX_SIZE` | | 2000 | Paragraph chunking max size |
| `EVIDENCE_TOP_K` | | 5 | Top K evidence to retrieve |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | | 0.5 | Min confidence for classification |

---

## Development

### Schema Migrations

Schema changes are managed by Alembic (never runtime `Base.metadata.create_all`):

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new column to cases"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Testing

Run tests with pytest (add test suite as needed):

```bash
pytest app/tests/
```

### Running Workers Locally

Start workers in a separate terminal:

```bash
python -m arq app.workers.settings.WorkerSettings
```

---

## Deployment

### Railway Deployment

LegalLanguageModels is configured for Railway via [`railway.toml`](railway.toml):

1. Connect your GitHub repository to Railway
2. Add environment variables in Railway dashboard
3. Railway auto-deploys on push to default branch

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Ensure all environment variables are set in Railway before deploying.

### Docker

Build and push custom image:

```bash
docker build -t legallanguagemodels:latest .
docker run -p 8000:8000 --env-file .env legallanguagemodels:latest
```

---

## Key Architectural Decisions

See [`docs/adr/`](docs/adr/) for detailed ADRs:

- **ADR-001**: Retrieval Before Classification
- **ADR-004**: Provenance-First Legal AI Architecture
- **ADR-007**: Knowledge Base as Parallel RAG Pipeline
- **ADR-014**: RAG 2 Template-Driven Generation Architecture
- **ADR-015**: Compute Once, Reuse Many — KB Deduplication

---

## Known Limitations & Next Steps

### Current Sprint Focus

- Multi-label classification
- Retrieval similarity thresholding
- JWT protection for retrieval endpoints

### Future Work

- Async task orchestration layer
- Graph database for evidence relationships
- Advanced generation (evidence-aware drafting)

---

## Support & Troubleshooting

### Health Check Failed

```bash
curl http://localhost:8000/health
```

If database or S3 check fails, verify:
- PostgreSQL is running: `docker-compose ps`
- Redis is healthy: `redis-cli ping`
- AWS credentials in `.env` are valid
- S3 bucket exists and is accessible

### Task Queue Issues

View failed tasks:

```bash
# Connect to Redis
redis-cli
LRANGE arq:failed 0 -1
```

Re-enqueue a failed task via admin endpoint.

### Database Migration Errors

Roll back to previous migration:

```bash
alembic downgrade -1
# Fix schema issue
alembic upgrade head
```

---

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and test locally
3. Submit a pull request

---

## License

See LICENSE file.

---

## Contact

For questions or issues, open a GitHub issue or contact the maintainers.
