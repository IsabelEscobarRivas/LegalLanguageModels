"""Enqueue helpers. Import these in route handlers to dispatch async tasks."""
import os
from arq import create_pool
from app.workers.settings import REDIS_SETTINGS


async def get_arq_pool():
    return await create_pool(REDIS_SETTINGS)


async def enqueue_ingest_document(
    pool,
    *,
    document_id: str,
    case_id: str,
    firm_id: str,
    version_id: str,
) -> str:
    """Enqueue document ingestion. Returns job_id."""
    job = await pool.enqueue_job(
        "ingest_document",
        document_id=document_id,
        case_id=case_id,
        firm_id=firm_id,
        version_id=version_id,
        _queue_name="llm_tasks",
    )
    return job.job_id


async def enqueue_ingest_kb_document(
    pool,
    *,
    kb_document_id: str,
    firm_id: str,
) -> str:
    """Enqueue KB document ingestion. Returns job_id."""
    job = await pool.enqueue_job(
        "ingest_kb_document",
        kb_document_id=kb_document_id,
        firm_id=firm_id,
        _queue_name="llm_tasks",
    )
    return job.job_id


async def enqueue_classify_document_version(
    pool,
    *,
    case_id: str,
    document_id: str,
    version_id: str,
    visa_type: str,
    firm_id: str,
    force_reclassify: bool = False,
) -> str:
    """Enqueue classification. Returns job_id."""
    job = await pool.enqueue_job(
        "classify_document_version",
        case_id=case_id,
        document_id=document_id,
        version_id=version_id,
        visa_type=visa_type,
        firm_id=firm_id,
        force_reclassify=force_reclassify,
        _queue_name="llm_tasks",
    )
    return job.job_id


async def replay_failed_job(
    pool,
    *,
    task_name: str,
    kwargs: dict,
) -> str:
    """Re-enqueue a failed task with the same kwargs.

    Caller is responsible for validating firm_id is present in kwargs
    before calling this. Never call without firm_id in kwargs.
    """
    job = await pool.enqueue_job(
        task_name,
        _queue_name="llm_tasks",
        **kwargs,
    )
    return job.job_id
