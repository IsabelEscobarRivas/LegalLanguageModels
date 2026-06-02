"""KB ingestion pipeline — chunk, embed, index.

Mirrors the case document ingestion pipeline pattern but operates on:
  KBDocument → KBChunk → KBEmbedding

All functions:
  - Validate firm_id before touching any row
  - Are idempotent (safe to call multiple times)
  - Never raise — return status dicts
  - Write ProcessingEvent rows for every transition
  - Advance KBDocument.lifecycle_state atomically with the data write

Public API:
  chunk_kb_document(db, kb_document_id, firm_id) -> dict
  embed_kb_document(db, kb_document_id, firm_id) -> dict
  index_kb_document(db, kb_document_id, firm_id) -> dict
"""
import logging
import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Optional

import PyPDF2
from docx import Document as DocxDocument

import openai
from sqlalchemy.orm import Session

from app.core.models import KBChunk, KBDocument, KBEmbedding, ProcessingEvent
from app.ingestion.chunker import chunk_text_paragraph
from app.ingestion.s3 import _bucket, _s3_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_MODEL_VERSION = os.environ.get("EMBEDDING_MODEL_VERSION", "1.0")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", 1536))


def _validate_kb_doc(db: Session, kb_document_id: str, firm_id: str) -> Optional[KBDocument]:
    """Return KBDocument if it exists and belongs to firm_id, else None."""
    return (
        db.query(KBDocument)
        .filter(
            KBDocument.id == kb_document_id,
            KBDocument.firm_id == firm_id,
        )
        .first()
    )


def _write_kb_event(
    db: Session,
    event_type: str,
    status: str,
    kb_document_id: str,
    firm_id: str,
    detail: dict,
    error_message: Optional[str] = None,
) -> None:
    """Write a ProcessingEvent for a KB pipeline stage. case_id is None."""
    event = ProcessingEvent(
        case_id=None,
        document_id=None,
        document_version_id=None,
        event_type=event_type,
        status=status,
        detail={"kb_document_id": kb_document_id, "firm_id": firm_id, **detail},
        error_message=error_message,
    )
    db.add(event)
    db.commit()


def chunk_kb_document(db: Session, kb_document_id: str, firm_id: str) -> dict:
    """Extract text from S3, chunk using paragraph strategy, persist KBChunk rows.

    Lifecycle: uploaded → chunked
    Idempotent: returns {"status": "exists"} if KBChunk rows already present.
    Never raises.
    """
    try:
        kb_doc = _validate_kb_doc(db, kb_document_id, firm_id)
        if kb_doc is None:
            return {"status": "failed", "reason": "firm_boundary_violation"}

        # Idempotency check
        from sqlalchemy import func
        existing_count = (
            db.query(func.count(KBChunk.id))
            .filter(KBChunk.kb_document_id == kb_document_id)
            .scalar()
        ) or 0
        if existing_count > 0:
            return {"status": "exists", "chunks_created": existing_count}

        # Fetch from S3 and extract text (format-aware)
        response = _s3_client().get_object(Bucket=_bucket(), Key=kb_doc.s3_key)
        raw_bytes = response["Body"].read()
        filename = kb_doc.s3_key.rsplit("/", 1)[-1] if kb_doc.s3_key else ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        try:
            if ext == "docx":
                doc = DocxDocument(BytesIO(raw_bytes))
                text = "\n".join(
                    p.text for p in doc.paragraphs if p.text.strip()
                )
            elif ext == "pdf":
                reader = PyPDF2.PdfReader(BytesIO(raw_bytes))
                text = "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            else:
                text = raw_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            _write_kb_event(
                db, "kb_chunking_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "extraction_failed"},
                error_message=str(exc),
            )
            return {"status": "failed", "reason": "extraction_failed"}

        # Strip NUL bytes defensively before chunking
        text = text.replace("\x00", "")

        if not text.strip():
            _write_kb_event(
                db, "kb_chunking_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "empty_text"},
                error_message="Extracted text is empty after strip",
            )
            return {"status": "failed", "reason": "empty_text"}

        pieces = chunk_text_paragraph(text)
        if not pieces:
            _write_kb_event(
                db, "kb_chunking_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "no_chunks_produced"},
            )
            return {"status": "failed", "reason": "no_chunks_produced"}

        chunk_objects = [
            KBChunk(
                id=str(uuid.uuid4()),
                firm_id=firm_id,
                kb_document_id=kb_document_id,
                chunk_index=p["chunk_index"],
                text=p["text"],
                chunk_strategy="paragraph",
            )
            for p in pieces
        ]
        db.bulk_save_objects(chunk_objects)

        kb_doc.lifecycle_state = "chunked"
        kb_doc.updated_at = datetime.utcnow()

        _write_kb_event(
            db, "kb_chunking_completed", "completed",
            kb_document_id, firm_id,
            {"chunks_created": len(pieces), "strategy": "paragraph"},
        )

        return {"status": "ok", "chunks_created": len(pieces)}

    except Exception as exc:
        logger.exception("chunk_kb_document failed kb_document_id=%s", kb_document_id)
        try:
            db.rollback()
        except Exception:
            pass
        _write_kb_event(
            db, "kb_chunking_failed", "failed",
            kb_document_id, firm_id,
            {"reason": "exception"},
            error_message=str(exc),
        )
        return {"status": "failed", "reason": str(exc)}


def embed_kb_document(db: Session, kb_document_id: str, firm_id: str) -> dict:
    """Embed all KBChunk rows, persist KBEmbedding rows.

    Lifecycle: chunked → embedded
    Idempotent: skips chunks that already have an embedding.
    Partial success keeps state at 'chunked' — retry will complete remaining.
    Never raises.
    """
    try:
        kb_doc = _validate_kb_doc(db, kb_document_id, firm_id)
        if kb_doc is None:
            return {"status": "failed", "reason": "firm_boundary_violation"}

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"status": "failed", "reason": "missing_api_key"}

        chunks = (
            db.query(KBChunk)
            .filter(
                KBChunk.kb_document_id == kb_document_id,
                KBChunk.firm_id == firm_id,
            )
            .order_by(KBChunk.chunk_index.asc())
            .all()
        )
        if not chunks:
            return {"status": "failed", "reason": "no_chunks"}

        client = openai.OpenAI(api_key=api_key)
        succeeded = 0
        failed = 0
        skipped = 0

        for chunk in chunks:
            existing = (
                db.query(KBEmbedding)
                .filter(KBEmbedding.kb_chunk_id == chunk.id)
                .first()
            )
            if existing:
                skipped += 1
                continue

            try:
                response = client.embeddings.create(
                    input=chunk.text,
                    model=EMBEDDING_MODEL,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
                vector = response.data[0].embedding
            except Exception as embed_exc:
                logger.exception("KB embedding failed for chunk %s", chunk.id)
                failed += 1
                continue

            db.add(KBEmbedding(
                id=str(uuid.uuid4()),
                firm_id=firm_id,
                kb_chunk_id=chunk.id,
                embedding=vector,
                model_name=EMBEDDING_MODEL,
            ))
            succeeded += 1

        if succeeded == 0 and failed > 0:
            try:
                db.rollback()
            except Exception:
                pass
            _write_kb_event(
                db, "kb_embedding_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "all_chunks_failed", "failed_count": failed},
            )
            return {"status": "failed", "reason": "all_chunks_failed"}

        if failed > 0:
            # Partial — commit what succeeded, stay at chunked
            db.commit()
            _write_kb_event(
                db, "kb_embedding_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "partial", "succeeded_count": succeeded, "failed_count": failed},
            )
            return {"status": "partial", "embeddings_created": succeeded, "failed_count": failed}

        kb_doc.lifecycle_state = "embedded"
        kb_doc.updated_at = datetime.utcnow()
        db.commit()

        _write_kb_event(
            db, "kb_embedding_completed", "completed",
            kb_document_id, firm_id,
            {"embeddings_created": succeeded, "model_name": EMBEDDING_MODEL},
        )
        return {"status": "ok", "embeddings_created": succeeded}

    except Exception as exc:
        logger.exception("embed_kb_document failed kb_document_id=%s", kb_document_id)
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "failed", "reason": str(exc)}


def index_kb_document(db: Session, kb_document_id: str, firm_id: str) -> dict:
    """Verify all chunks have embeddings and advance lifecycle to indexed.

    Lifecycle: embedded → indexed
    Idempotent: safe to call if already indexed.
    Never raises.
    """
    try:
        kb_doc = _validate_kb_doc(db, kb_document_id, firm_id)
        if kb_doc is None:
            return {"status": "failed", "reason": "firm_boundary_violation"}

        if kb_doc.lifecycle_state == "indexed":
            return {"status": "ok", "note": "already_indexed"}

        from sqlalchemy import func
        chunk_count = (
            db.query(func.count(KBChunk.id))
            .filter(KBChunk.kb_document_id == kb_document_id)
            .scalar()
        ) or 0

        embedding_count = (
            db.query(func.count(KBEmbedding.id))
            .join(KBChunk, KBChunk.id == KBEmbedding.kb_chunk_id)
            .filter(KBChunk.kb_document_id == kb_document_id)
            .scalar()
        ) or 0

        if chunk_count == 0:
            _write_kb_event(
                db, "kb_indexing_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "no_chunks", "chunk_count": 0},
            )
            return {"status": "failed", "reason": "no_chunks"}

        if embedding_count < chunk_count:
            missing = chunk_count - embedding_count
            _write_kb_event(
                db, "kb_indexing_failed", "failed",
                kb_document_id, firm_id,
                {"reason": "embedding_incomplete", "missing_count": missing,
                 "chunk_count": chunk_count, "embedding_count": embedding_count},
            )
            return {"status": "failed", "reason": "embedding_incomplete", "missing_count": missing}

        kb_doc.lifecycle_state = "indexed"
        kb_doc.updated_at = datetime.utcnow()
        db.commit()

        _write_kb_event(
            db, "kb_indexing_completed", "completed",
            kb_document_id, firm_id,
            {"indexed_chunks": chunk_count},
        )
        return {"status": "ok", "indexed_chunks": chunk_count}

    except Exception as exc:
        logger.exception("index_kb_document failed kb_document_id=%s", kb_document_id)
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "failed", "reason": str(exc)}
