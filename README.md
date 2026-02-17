# Immigration Document Intelligence System
### AI-Powered Document Processing for EB1 & EB2 Visa Applications

> A production-grade, multi-tenant platform that applies LLMs and RAG to automate document classification, extraction, and retrieval for U.S. immigration law firms — built in two iterations from prototype to enterprise architecture.

---

## What This Project Does

Immigration attorneys processing EB1 and EB2 visa applications deal with hundreds of unstructured documents per case — recommendation letters, published research, employment records, awards, and more. Each document must be correctly classified against USCIS evidentiary criteria before it can be used in a petition.

This system automates that process using LLMs and Retrieval-Augmented Generation (RAG), turning a manual, error-prone workflow into an intelligent pipeline that:

- **Classifies** uploaded documents against EB1/EB2 USCIS criteria automatically
- **Extracts** structured data from unstructured PDFs and DOCX files
- **Retrieves** the most relevant precedent documents for a given case using semantic search
- **Scales** across multiple law firms with full data isolation per tenant

---

## Architecture Evolution: V1 → V2

This repository tells the story of a system built iteratively — from a working prototype to a production-ready platform.

### V1 — Prototype (`/v1`)
*Single-tenant document ingestion and RAG pipeline*

The first version established the core intelligence layer:

- **FastAPI** backend with S3 document storage
- **LLM-powered text extraction** from PDFs and DOCX files
- **Custom RAG implementation** (`ket_rag/`) for semantic document retrieval
- **EB1/EB2 taxonomy** encoded as structured enums aligned to USCIS criteria
- React/HTML frontend for case and document management

The RAG corpus is built per-case, with similarity-based chunking that creates semantic connections between related documents. This was the foundation for understanding how immigration documents relate to one another within a visa petition.

**Tech stack:** Python · FastAPI · SQLAlchemy · AWS S3 · Custom RAG · HTML/JS frontend

---

### V2 — Production Architecture (`/v2`)
*Multi-tenant, role-based enterprise platform*

V2 re-architected the system from the ground up for real-world law firm deployment:

**Multi-tenancy**
- Full data isolation per law firm via `law_firm_id` on every database table
- One deployment serves many firms; no firm can access another's data or knowledge base
- Firm-scoped RAG corpora — each firm's system gets smarter with their own data over time

**Security & Permissions**
- JWT authentication with role-based access control
- Permission hierarchy: `Paralegal < Associate < Partner < Admin`
- All API endpoints enforce both authentication and tenant scoping

**Clean Architecture**
- Separated into Domain, Application, and Infrastructure layers
- 47/47 tests passing across domain logic and security validation
- SQLite for development; PostgreSQL-ready for production

**Competitive Moat by Design**
- Each firm accumulates a proprietary knowledge base from their own successful petitions
- Letter generation uses firm-specific RAG + firm-uploaded templates
- Success tracking feeds back into continuous learning per firm

**Tech stack:** Python · FastAPI · SQLAlchemy · JWT · PostgreSQL · Multi-tenant RAG · Role-based access control

---

## Key Technical Highlights

| Capability | Implementation |
|---|---|
| Document ingestion | PDF + DOCX parsing with LLM-assisted extraction |
| Document classification | LLM classification against USCIS EB1/EB2 criteria taxonomy |
| Semantic retrieval | Custom RAG with similarity-based chunk connections |
| Multi-tenancy | Row-level isolation, firm-scoped knowledge bases |
| Auth | JWT tokens with 4-tier RBAC |
| Test coverage | 47/47 tests (domain + security) |
| Storage | AWS S3 for documents, SQL for metadata |

---

## Why This Matters for AI/Data Science Roles

This project reflects the kind of applied AI engineering work that produces real-world impact:

- **Messy, unstructured data at the source** — immigration documents are inconsistently formatted, multilingual, and legally precise. Getting LLMs to classify them reliably required domain-specific taxonomy design, not just off-the-shelf prompting.
- **RAG in production** — the retrieval system needed to respect case boundaries, visa type hierarchies, and firm data isolation simultaneously.
- **Iterative system design** — V1 proved the concept; V2 hardened it for deployment. Both are included because the progression shows engineering judgment, not just code.
- **Domain expertise embedded in architecture** — the EB1/EB2 taxonomy, USCIS evidentiary categories, and firm-level knowledge accumulation are features born from deep domain understanding.

---

## Repository Structure

```
/
├── v1/                         # Prototype — single-tenant pipeline
│   ├── app/
│   │   ├── main.py             # FastAPI application
│   │   ├── models.py           # Document + case data models
│   │   ├── schemas.py          # EB1/EB2 taxonomy as Pydantic enums
│   │   ├── ket_rag/            # Custom RAG implementation
│   │   │   ├── corpus_builder.py
│   │   │   └── core.py
│   │   └── services/           # Business logic
│   └── static/                 # Frontend (HTML/JS/CSS)
│
└── v2/                         # Production — multi-tenant enterprise
    ├── domain/                 # Core business logic (tenant-agnostic)
    ├── application/            # Use cases and orchestration
    ├── infrastructure/         # DB, auth, external services
    ├── api/                    # FastAPI routes (/api/v2/*)
    └── tests/                  # 47 passing tests
```

---

## Running Locally

### V1
```bash
cd v1
pip install -r requirements.txt
uvicorn app.main:app --reload
# API docs at http://localhost:8000/docs
```

### V2
```bash
cd v2
pip install -r requirements.txt
# Set environment variables (see .env.example)
uvicorn main:app --reload
# Auth: POST /auth/login
# Docs: http://localhost:8000/docs
```

---

## About

Built by **Isabel Escobar Rivas** as Product Owner and lead developer, working at the intersection of legal domain expertise and applied AI engineering.

- [LinkedIn](https://www.linkedin.com/in/isabelescobarr/)
- [Portfolio](https://isabelescobarrivas.myportfolio.com/)
