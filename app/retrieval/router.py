"""Sprint 2 retrieval endpoints.

Three protected endpoints (all gated by `Depends(require_case_access)`):

    POST /cases/{case_id}/documents/{document_id}/versions/{version_id}/chunks
    POST /cases/{case_id}/documents/{document_id}/versions/{version_id}/embeddings
    POST /cases/{case_id}/retrieve

The triggers thinly wrap the chunker/embedder service functions and translate
their status dicts to HTTP. The `/retrieve` endpoint embeds the query via
OpenAI, runs a pgvector cosine-similarity search scoped to the latest version
of every document in the case, and appends a `RetrievalLog` row.
"""
import logging
import os

import openai
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import require_case_access
from app.core.database import get_db
from app.core.models import (
    Chunk,
    Document,
    DocumentVersion,
    Embedding,
    RetrievalLog,
)
from app.core.schemas import RetrieveRequest
from app.ingestion.chunker import chunk_document_version
from app.ingestion.embedder import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    embed_document_version,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["retrieval"])


@router.post(
    "/cases/{case_id}/documents/{document_id}/versions/{version_id}/chunks",
    status_code=202,
)
def trigger_chunking(
    *,
    case_id: str = Depends(require_case_access),
    document_id: str,
    version_id: str,
    strategy: str = Query(default='fixed_size'),
    db: Session = Depends(get_db),
):
    """Trigger chunking for a DocumentVersion. Idempotent on (strategy, version)."""
    if strategy not in ('fixed_size', 'paragraph'):
        raise HTTPException(status_code=422, detail="Invalid strategy")

    result = chunk_document_version(
        db, case_id, document_id, version_id, strategy=strategy
    )
    status_val = result["status"]

    if status_val == "ok":
        return {
            "version_id": result["version_id"],
            "chunks_created": result["chunks_created"],
            "chunk_strategy": result["chunk_strategy"],
            "chunk_strategy_version": result["chunk_strategy_version"],
        }
    if status_val == "exists":
        raise HTTPException(
            status_code=409,
            detail="Chunks already exist for this version and strategy",
        )
    if status_val == "not_found":
        raise HTTPException(status_code=404, detail="Version not found")
    if status_val == "failed":
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Chunking failed"),
        )

    logger.error("Unexpected status from chunk_document_version: %r", status_val)
    raise HTTPException(status_code=500, detail="Internal error")


@router.post(
    "/cases/{case_id}/documents/{document_id}/versions/{version_id}/embeddings",
    status_code=202,
)
def trigger_embedding(
    *,
    case_id: str = Depends(require_case_access),
    document_id: str,
    version_id: str,
    db: Session = Depends(get_db),
):
    """Trigger embedding for every chunk of a DocumentVersion."""
    # Pre-check: chunks must exist for this version, scoped to this case.
    chunks_exist = (
        db.query(Chunk.id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .join(Document, Document.id == DocumentVersion.document_id)
        .filter(Chunk.document_version_id == version_id)
        .filter(Document.case_id == case_id)
        .first()
    )
    if chunks_exist is None:
        raise HTTPException(
            status_code=422,
            detail="No chunks exist for this version. Run chunking first.",
        )

    result = embed_document_version(db, case_id, document_id, version_id)
    status_val = result["status"]

    if status_val == "ok":
        return {
            "version_id": result["version_id"],
            "embeddings_created": result["embeddings_created"],
            "model_name": result["model_name"],
            "model_version": result["model_version"],
        }
    if status_val == "partial":
        return {
            "version_id": result["version_id"],
            "embeddings_created": result["embeddings_created"],
            "failed_count": result["failed_count"],
            "model_name": result["model_name"],
            "model_version": result["model_version"],
        }
    if status_val == "not_found":
        raise HTTPException(status_code=404, detail="Version not found")
    if status_val == "failed":
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Embedding failed"),
        )

    logger.error("Unexpected status from embed_document_version: %r", status_val)
    raise HTTPException(status_code=500, detail="Internal error")


@router.post("/cases/{case_id}/retrieve")
def retrieve(
    *,
    case_id: str = Depends(require_case_access),
    body: RetrieveRequest,
    db: Session = Depends(get_db),
):
    """Cosine-similarity retrieval over the latest version of every document
    in the case. Always returns a list (empty when no embeddings match)."""

    # ---- Step A: embed the query ---------------------------------------
    try:
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.embeddings.create(
            input=body.query,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        query_vector = response.data[0].embedding
    except Exception:
        logger.exception("Query embedding failed for case %s", case_id)
        raise HTTPException(status_code=503, detail="Query embedding failed")

    # ---- Steps B-F: DB-side search + log -------------------------------
    try:
        # Step B: latest DocumentVersion per document in this case.
        latest_versions = (
            db.query(
                DocumentVersion.document_id,
                func.max(DocumentVersion.version_number).label("max_version"),
            )
            .join(Document, Document.id == DocumentVersion.document_id)
            .filter(Document.case_id == case_id)
            .group_by(DocumentVersion.document_id)
            .subquery()
        )

        latest_version_ids = (
            db.query(DocumentVersion.id)
            .join(
                latest_versions,
                (DocumentVersion.document_id == latest_versions.c.document_id)
                & (DocumentVersion.version_number == latest_versions.c.max_version),
            )
            .all()
        )
        version_id_list = [r[0] for r in latest_version_ids]

        # Step C: pgvector cosine similarity over chunks in those versions.
        result_list: list[dict] = []
        if version_id_list:
            sim_score = (
                1 - Embedding.vector.cosine_distance(query_vector)
            ).label("similarity_score")

            rows = (
                db.query(
                    Embedding,
                    Chunk,
                    DocumentVersion,
                    Document,
                    sim_score,
                )
                .join(Chunk, Chunk.id == Embedding.chunk_id)
                .join(
                    DocumentVersion,
                    DocumentVersion.id == Chunk.document_version_id,
                )
                .join(Document, Document.id == DocumentVersion.document_id)
                .filter(Chunk.document_version_id.in_(version_id_list))
                .filter(Document.case_id == case_id)
                .order_by(sim_score.desc())
                .limit(body.top_k)
                .all()
            )

            # Step D: provenance-complete result rows — every field required.
            for embedding, chunk, version, document, score in rows:
                result_list.append(
                    {
                        "chunk_id": chunk.id,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                        "similarity_score": float(score),
                        "document_id": document.id,
                        "document_version_id": version.id,
                        "version_number": version.version_number,
                        "original_name": document.original_name,
                        "case_id": case_id,
                    }
                )

        # Apply min_similarity threshold post-query. pgvector cosine-distance
        # operators do not filter cleanly at the SQL layer without index
        # changes; post-query filtering is correct here. When min_similarity
        # is 0.0 the filter is skipped so behavior is identical to pre-S3-D01.
        if body.min_similarity > 0.0:
            result_list = [
                r for r in result_list
                if r["similarity_score"] >= body.min_similarity
            ]

        # Step E: append RetrievalLog (always, even for empty results).
        # results_count is the post-threshold count, per S3-D01.
        log = RetrievalLog(
            case_id=case_id,
            query_text=body.query,
            query_embedding_id=None,  # Sprint 2 does not store query embeddings
            top_k=body.top_k,
            min_similarity=body.min_similarity,
            results_count=len(result_list),
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        # Step F: response.
        return {
            "case_id": case_id,
            "query": body.query,
            "results": result_list,
            "retrieval_log_id": log.id,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Retrieval failed for case %s", case_id)
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback after retrieval failure also failed")
        raise HTTPException(status_code=503, detail="Retrieval failed")
