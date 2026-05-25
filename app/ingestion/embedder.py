"""Embedding pipeline for Sprint 2.

Calls the OpenAI Embeddings API once per chunk and persists an `Embedding` row
per successful call. The `embeddings` table is append-only — existing rows for
the same chunk + model_name + model_version are skipped silently and never
overwritten.

Public API:
  - embed_document_version(db, case_id, document_id, version_id) : never raises

Event taxonomy: embedding_completed, embedding_failed
"""
import logging
import os
import uuid
from datetime import datetime

import openai
from sqlalchemy.orm import Session

from app.core.models import (
    Chunk,
    Document,
    DocumentVersion,
    Embedding,
    ProcessingEvent,
)
from app.ingestion.events import write_event


logger = logging.getLogger(__name__)


EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_MODEL_VERSION = os.environ.get("EMBEDDING_MODEL_VERSION", "1.0")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", 1536))


def embed_document_version(
    db: Session,
    case_id: str,
    document_id: str,
    version_id: str,
) -> dict:
    """Embed every chunk of a DocumentVersion. Never raises.

    Return shapes:
      * status='ok'      : every attempted chunk embedded (skipped chunks are
                           treated as success — already embedded with this
                           model/version)
      * status='partial' : at least one succeeded AND at least one failed
      * status='failed'  : reason in {'missing_api_key', 'no_chunks',
                           'all_chunks_failed', <exception str>}
      * status='not_found' : the case -> document -> version chain is broken

    Idempotency: per-chunk check on (chunk_id, model_name, model_version).
    Existing embeddings are silently skipped — never overwritten.
    """
    try:
        # Spec rule: do not even attempt the OpenAI call without a key.
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            write_event(
                db,
                event_type="embedding_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={"reason": "missing_api_key"},
                error_message="OPENAI_API_KEY is not set",
            )
            return {"status": "failed", "reason": "missing_api_key"}

        # 1. Verify the case -> document -> version ownership chain.
        document = (
            db.query(Document)
            .filter(Document.id == document_id, Document.case_id == case_id)
            .first()
        )
        if document is None:
            return {"status": "not_found"}

        version = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.id == version_id,
                DocumentVersion.document_id == document_id,
            )
            .first()
        )
        if version is None:
            return {"status": "not_found"}

        # 2. Fetch all chunks ordered by chunk_index ascending.
        chunks = (
            db.query(Chunk)
            .filter(Chunk.document_version_id == version_id)
            .order_by(Chunk.chunk_index.asc())
            .all()
        )
        if not chunks:
            write_event(
                db,
                event_type="embedding_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={"reason": "no_chunks"},
                error_message="No chunks exist for this DocumentVersion",
            )
            return {"status": "failed", "reason": "no_chunks"}

        # 3. Embed each chunk, skipping any already embedded with this
        #    (model_name, model_version) pair. Per-chunk failures do not abort
        #    the batch — they accumulate into failed_count.
        client = openai.OpenAI(api_key=api_key)

        succeeded_count = 0
        failed_count = 0
        skipped_count = 0

        for chunk in chunks:
            existing = (
                db.query(Embedding)
                .filter(
                    Embedding.chunk_id == chunk.id,
                    Embedding.model_name == EMBEDDING_MODEL,
                    Embedding.model_version == EMBEDDING_MODEL_VERSION,
                )
                .first()
            )
            if existing:
                skipped_count += 1
                continue

            try:
                response = client.embeddings.create(
                    input=chunk.text,
                    model=EMBEDDING_MODEL,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
                vector = response.data[0].embedding
            except Exception as embed_exc:
                logger.exception(
                    "Embedding API failed for chunk %s", chunk.id
                )
                failed_count += 1
                continue

            embedding_row = Embedding(
                id=str(uuid.uuid4()),
                chunk_id=chunk.id,
                model_name=EMBEDDING_MODEL,
                model_version=EMBEDDING_MODEL_VERSION,
                dimensions=EMBEDDING_DIMENSIONS,
                vector=vector,
            )
            db.add(embedding_row)
            succeeded_count += 1

        # 4. Decide outcome based on counters.
        # Case A: every attempted chunk failed -> total failure, nothing to commit.
        if succeeded_count == 0 and failed_count > 0:
            try:
                db.rollback()
            except Exception:
                logger.exception(
                    "Rollback after all-chunks-failed also failed"
                )
            write_event(
                db,
                event_type="embedding_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={
                    "reason": "all_chunks_failed",
                    "failed_count": failed_count,
                    "succeeded_count": succeeded_count,
                },
                error_message="Every chunk embedding call failed",
            )
            return {"status": "failed", "reason": "all_chunks_failed"}

        # Case B: at least one success (and possibly some failures/skips).
        # Inline the event + lifecycle update so the single commit covers
        # embeddings + event + lifecycle atomically (same pattern as chunker).
        if succeeded_count > 0 or failed_count > 0:
            if failed_count > 0:
                event_type = "embedding_failed"
                event_status = "failed"
                event_detail = {
                    "failed_count": failed_count,
                    "succeeded_count": succeeded_count,
                    "model_name": EMBEDDING_MODEL,
                    "model_version": EMBEDDING_MODEL_VERSION,
                    "dimensions": EMBEDDING_DIMENSIONS,
                }
                event_error = (
                    f"{failed_count} of "
                    f"{failed_count + succeeded_count} chunks failed to embed"
                )
            else:
                event_type = "embedding_completed"
                event_status = "completed"
                event_detail = {
                    "embeddings_created": succeeded_count,
                    "model_name": EMBEDDING_MODEL,
                    "model_version": EMBEDDING_MODEL_VERSION,
                    "dimensions": EMBEDDING_DIMENSIONS,
                }
                event_error = None

            event = ProcessingEvent(
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                event_type=event_type,
                status=event_status,
                detail=event_detail,
                error_message=event_error,
            )
            db.add(event)

        # Lifecycle update only if at least one embedding actually succeeded.
        if succeeded_count > 0:
            document.lifecycle_state = "embedded"
            document.updated_at = datetime.utcnow()

        # Single commit for embeddings + event + lifecycle.
        db.commit()

        if failed_count > 0:
            return {
                "status": "partial",
                "version_id": version_id,
                "embeddings_created": succeeded_count,
                "failed_count": failed_count,
                "model_name": EMBEDDING_MODEL,
                "model_version": EMBEDDING_MODEL_VERSION,
            }

        return {
            "status": "ok",
            "version_id": version_id,
            "embeddings_created": succeeded_count,
            "model_name": EMBEDDING_MODEL,
            "model_version": EMBEDDING_MODEL_VERSION,
        }

    except Exception as exc:
        logger.exception(
            "Embedding failed unexpectedly for version %s", version_id
        )
        # Discard any pending session state from the partial flow BEFORE we
        # try to write the failure event — otherwise write_event's internal
        # commit would also commit the half-written state.
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after embedding failure also failed")
        write_event(
            db,
            event_type="embedding_failed",
            status="failed",
            case_id=case_id,
            document_id=document_id,
            document_version_id=version_id,
            detail={"reason": "exception"},
            error_message=str(exc),
        )
        return {"status": "failed", "reason": str(exc)}
