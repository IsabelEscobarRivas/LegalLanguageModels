"""ARQ worker settings."""
import os
from arq.connections import RedisSettings

from app.workers.tasks import (
    classify_document_version,
    ingest_document,
    ingest_kb_document,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# Parse redis://host:port
_parts = REDIS_URL.replace("redis://", "").split(":")
REDIS_HOST = _parts[0]
REDIS_PORT = int(_parts[1]) if len(_parts) > 1 else 6379

REDIS_SETTINGS = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)


class WorkerSettings:
    functions = [
        ingest_document,
        ingest_kb_document,
        classify_document_version,
    ]
    redis_settings = REDIS_SETTINGS
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    max_tries = 3
    retry_failed_jobs = True
    queue_name = "llm_tasks"
