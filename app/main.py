"""V2 application entry point (thin shell).

Responsibilities, and nothing else:
  - construct the FastAPI app and CORS
  - mount static assets and serve the frontend entry point
  - register API routers (cases, documents, retrieval, events)
  - expose /health (DB SELECT 1 + S3 head_bucket)

Schema management is owned entirely by Alembic. `alembic upgrade head` runs
ahead of uvicorn at container start (see `docker-compose.yml`). There is no
runtime `Base.metadata.create_all` here — a legal/audit platform must have a
single source of truth for schema state.

All V1 business logic — inline S3, extraction, taxonomy tables, document
routes — now lives in `app.api.*` and `app.ingestion.*`.
"""
import logging
import os

import boto3
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.cases.router import router as cases_router
from app.api.documents.router import router as documents_router
from app.api.events.router import router as events_router
from app.classification.router import router as classification_router
from app.core import models  # noqa: F401 - register models on Base.metadata
from app.core.database import get_db
from app.retrieval.router import router as retrieval_router


logger = logging.getLogger(__name__)

app = FastAPI(title="LegalLanguageModels V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(cases_router)
app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(events_router)
app.include_router(classification_router)


@app.get("/")
async def root():
    """Serve the frontend SPA entry point."""
    return FileResponse("static/index.html")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness + readiness: DB SELECT 1 and S3 head_bucket.

    Returns 200 with {status, database, s3} when both checks pass,
    503 with the same shape (inside `detail`) when either fails.
    Error specifics are logged server-side, not returned, so this
    endpoint never leaks credentials or backend internals.
    """
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check: database SELECT 1 failed")

    s3_ok = False
    try:
        bucket = os.environ.get("S3_BUCKET_NAME")
        if not bucket:
            raise RuntimeError("S3_BUCKET_NAME is not configured")
        client = boto3.client(
            "s3",
            region_name=os.environ.get("AWS_REGION", "us-east-2"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
        client.head_bucket(Bucket=bucket)
        s3_ok = True
    except Exception:
        logger.exception("Health check: S3 head_bucket failed")

    body = {
        "status": "ok" if db_ok and s3_ok else "error",
        "database": "ok" if db_ok else "error",
        "s3": "ok" if s3_ok else "error",
    }
    if not (db_ok and s3_ok):
        raise HTTPException(status_code=503, detail=body)
    return body
