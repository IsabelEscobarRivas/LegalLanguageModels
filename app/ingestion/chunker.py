"""Fixed-size chunking pipeline for Sprint 2.

Module-level configuration is read from env vars at import time and applied to
every chunking call. Output is fully deterministic for a given (text, config)
pair.

Public API:
  - chunk_text(text)                              : pure splitter, no DB
  - chunk_document_version(db, case, doc, ver)    : DB-orchestrating, never raises

Event taxonomy: chunking_completed, chunking_failed
"""
import logging
import os
import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.models import Chunk, Document, DocumentVersion, ProcessingEvent
from app.ingestion.events import write_event
from app.ingestion.s3 import _bucket, _s3_client


logger = logging.getLogger(__name__)


CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 512))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 50))
MIN_CHUNK_SIZE = int(os.environ.get("MIN_CHUNK_SIZE", 100))
PARAGRAPH_MIN_SIZE = int(os.environ.get("PARAGRAPH_MIN_SIZE", 50))
PARAGRAPH_MAX_SIZE = int(os.environ.get("PARAGRAPH_MAX_SIZE", 2000))
CHUNK_STRATEGY = "fixed_size"
CHUNK_STRATEGY_VERSION = "1.0"


def chunk_text(text: str) -> list[dict]:
    """Split text into overlapping windows of CHUNK_SIZE characters.

    Algorithm:
      - Sliding window with stride CHUNK_SIZE - CHUNK_OVERLAP.
      - If the final chunk is below MIN_CHUNK_SIZE, merge it into the
        preceding chunk (the preceding chunk may end up larger than
        CHUNK_SIZE as a result).
      - Returns an empty list for empty or whitespace-only input.
      - Deterministic: identical input + config -> identical output.
      - Never raises.

    Each returned dict has the keys:
        text         (str)
        char_start   (int)
        char_end     (int)
        chunk_index  (int, 0-based)
    """
    if not text or not text.strip():
        return []

    # Defensive: if overlap >= size the stride would be <= 0 and we'd loop
    # forever. Clamp to at least one character per step. This never triggers
    # for valid config (CHUNK_OVERLAP << CHUNK_SIZE).
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)

    chunks: list[dict] = []
    n = len(text)
    start = 0
    chunk_index = 0

    while start < n:
        end = min(start + CHUNK_SIZE, n)
        chunks.append(
            {
                "text": text[start:end],
                "char_start": start,
                "char_end": end,
                "chunk_index": chunk_index,
            }
        )
        chunk_index += 1
        if end >= n:
            break
        start += step

    # Merge a final under-min chunk into the previous one if there is one.
    if len(chunks) > 1 and len(chunks[-1]["text"]) < MIN_CHUNK_SIZE:
        tail = chunks.pop()
        prev = chunks[-1]
        prev["text"] = text[prev["char_start"] : tail["char_end"]]
        prev["char_end"] = tail["char_end"]

    return chunks


def chunk_text_paragraph(text: str) -> list[dict]:
    """Split text at paragraph boundaries.

    Rules:
    - Split on double newline (\\n\\n) or single newline followed by whitespace
    - Merge any paragraph below PARAGRAPH_MIN_SIZE into the preceding paragraph
    - Split any paragraph above PARAGRAPH_MAX_SIZE at the nearest sentence
      boundary ('. ', '? ', '! ') before the max size limit
    - Returns list of {text, char_start, char_end, chunk_index}
    - Deterministic — same input always produces same output
    - Never raises — returns empty list if text is empty or whitespace only
    """
    if not text or not text.strip():
        return []

    # Split on paragraph boundaries
    import re
    raw_paragraphs = re.split(r'\n\n+|\n(?=\s)', text)
    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    if not paragraphs:
        return []

    # Merge short paragraphs into preceding
    merged = []
    for para in paragraphs:
        if merged and len(para) < PARAGRAPH_MIN_SIZE:
            merged[-1] = merged[-1] + ' ' + para
        else:
            merged.append(para)

    # Split oversized paragraphs at sentence boundaries
    final_paragraphs = []
    for para in merged:
        if len(para) <= PARAGRAPH_MAX_SIZE:
            final_paragraphs.append(para)
        else:
            # Split at sentence boundary before max size
            remaining = para
            while len(remaining) > PARAGRAPH_MAX_SIZE:
                split_at = PARAGRAPH_MAX_SIZE
                for punct in ['. ', '? ', '! ']:
                    idx = remaining.rfind(punct, 0, PARAGRAPH_MAX_SIZE)
                    if idx != -1 and idx > split_at // 2:
                        split_at = idx + len(punct)
                        break
                final_paragraphs.append(remaining[:split_at].strip())
                remaining = remaining[split_at:].strip()
            if remaining:
                final_paragraphs.append(remaining)

    # Build result with char offsets
    results = []
    pos = 0
    for idx, para in enumerate(final_paragraphs):
        # Find actual position in original text
        start = text.find(para, pos)
        if start == -1:
            start = pos
        end = start + len(para)
        results.append({
            'text': para,
            'char_start': start,
            'char_end': end,
            'chunk_index': idx,
        })
        pos = end

    return results


def chunk_document_version(
    db: Session,
    case_id: str,
    document_id: str,
    version_id: str,
    strategy: str = 'fixed_size',
) -> dict:
    """Chunk a DocumentVersion's extracted text and persist as Chunk rows.

    Returns a status dict (never raises). The router maps:
      * status='ok'                                        -> 200
      * status='not_found'                                 -> 404
      * status='exists'                                    -> 409
      * status='failed', reason='extraction_unavailable'   -> 503
      * status='failed', reason='empty_text'               -> 503
      * status='failed', reason=<exception str>            -> 500
    """
    try:
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

        if strategy == 'paragraph':
            strategy_version = '1.0'
            chunk_strategy = 'paragraph'
        else:
            strategy_version = CHUNK_STRATEGY_VERSION
            chunk_strategy = CHUNK_STRATEGY

        # 2. Idempotency — same strategy+version already produced chunks.
        existing_count = (
            db.query(func.count(Chunk.id))
            .filter(
                Chunk.document_version_id == version_id,
                Chunk.chunk_strategy == chunk_strategy,
                Chunk.chunk_strategy_version == strategy_version,
            )
            .scalar()
        ) or 0
        if existing_count > 0:
            return {"status": "exists", "chunks_created": existing_count}

        # 3. Fetch extracted text from S3.
        if not version.extracted_text_s3_key:
            write_event(
                db,
                event_type="chunking_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={"reason": "extraction_unavailable"},
                error_message="DocumentVersion.extracted_text_s3_key is null",
            )
            return {"status": "failed", "reason": "extraction_unavailable"}

        try:
            response = _s3_client().get_object(
                Bucket=_bucket(),
                Key=version.extracted_text_s3_key,
            )
            text = response["Body"].read().decode("utf-8")
        except Exception as s3_exc:
            logger.exception(
                "Failed to fetch extracted text from S3 (key=%s)",
                version.extracted_text_s3_key,
            )
            write_event(
                db,
                event_type="chunking_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={"reason": "extraction_unavailable"},
                error_message=str(s3_exc),
            )
            return {"status": "failed", "reason": "extraction_unavailable"}

        # 4. Empty-text gate after fetching.
        if not text.strip():
            write_event(
                db,
                event_type="chunking_failed",
                status="failed",
                case_id=case_id,
                document_id=document_id,
                document_version_id=version_id,
                detail={"reason": "empty_text"},
                error_message="Extracted text is empty after strip",
            )
            return {"status": "failed", "reason": "empty_text"}

        # 5. Split.
        if strategy == 'paragraph':
            pieces = chunk_text_paragraph(text)
        else:
            pieces = chunk_text(text)
        chunks_created = len(pieces)

        chunk_objects = [
            Chunk(
                id=str(uuid.uuid4()),
                document_version_id=version_id,
                chunk_index=p["chunk_index"],
                text=p["text"],
                char_start=p["char_start"],
                char_end=p["char_end"],
                chunk_strategy=chunk_strategy,
                chunk_strategy_version=strategy_version,
            )
            for p in pieces
        ]

        # 6. Single bulk insert — no per-chunk commits.
        db.bulk_save_objects(chunk_objects)

        # 7. chunking_completed event added inline so it commits with the
        #    chunks and the lifecycle update — one DB commit for the trio.
        event = ProcessingEvent(
            case_id=case_id,
            document_id=document_id,
            document_version_id=version_id,
            event_type="chunking_completed",
            status="completed",
            detail={
                "chunks_created": chunks_created,
                "chunk_strategy": chunk_strategy,
                "chunk_strategy_version": strategy_version,
            },
        )
        db.add(event)

        # 8. Lifecycle update on Document (Document is not append-only).
        document.lifecycle_state = "chunked"
        document.updated_at = datetime.utcnow()

        # 9. Single commit for bulk insert + event + lifecycle update.
        db.commit()

        return {
            "status": "ok",
            "version_id": version_id,
            "chunks_created": chunks_created,
            "chunk_strategy": chunk_strategy,
            "chunk_strategy_version": strategy_version,
        }

    except Exception as exc:
        logger.exception(
            "Chunking failed unexpectedly for version %s", version_id
        )
        # Discard any pending writes from the failed flow BEFORE we try to
        # write the failure event — otherwise write_event's commit would
        # also commit the half-written state.
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after chunking failure also failed")
        write_event(
            db,
            event_type="chunking_failed",
            status="failed",
            case_id=case_id,
            document_id=document_id,
            document_version_id=version_id,
            detail={"reason": "exception"},
            error_message=str(exc),
        )
        return {"status": "failed", "reason": str(exc)}
