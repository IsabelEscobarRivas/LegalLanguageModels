"""Case-level endpoints.

POST /cases
GET  /cases
GET  /cases/{case_id}/documents
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import TokenClaims, get_current_claims, require_case_access
from app.core.database import get_db
from app.core.models import Case, Chunk, Document, DocumentVersion
from app.core.schemas import (
    CaseCreate,
    CaseDocumentList,
    CaseListResponse,
    CaseResponse,
    DocumentSummary,
)


router = APIRouter(tags=["cases"])


@router.get("/cases", response_model=CaseListResponse)
def list_cases(
    *,
    db: Session = Depends(get_db),
    claims: TokenClaims = Depends(get_current_claims),
) -> CaseListResponse:
    cases = (
        db.query(Case)
        .filter(Case.firm_id == claims.firm_id)
        .order_by(Case.created_at.desc())
        .all()
    )
    return CaseListResponse(cases=cases)


@router.post("/cases", response_model=CaseResponse, status_code=201)
def create_case(
    *,
    payload: CaseCreate,
    db: Session = Depends(get_db),
    claims: TokenClaims = Depends(get_current_claims),
) -> CaseResponse:
    case = Case(
        case_ref=payload.case_ref,
        visa_type=payload.visa_type,
        firm_id=claims.firm_id,
        applicant_name=payload.applicant_name,
    )
    db.add(case)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"case_ref '{payload.case_ref}' already exists",
        )
    db.refresh(case)
    return case


@router.get("/cases/{case_id}/documents", response_model=CaseDocumentList)
def list_case_documents(
    *,
    case_id: str = Depends(require_case_access),
    db: Session = Depends(get_db),
) -> CaseDocumentList:
    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    rows = (
        db.query(Document, func.count(DocumentVersion.id).label("version_count"))
        .outerjoin(DocumentVersion, DocumentVersion.document_id == Document.id)
        .filter(Document.case_id == case_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    document_ids = [doc.id for doc, _ in rows]
    latest_by_doc: dict[str, DocumentVersion] = {}
    chunk_counts: dict[str, int] = {}

    if document_ids:
        latest_version_sq = (
            db.query(
                DocumentVersion.document_id,
                func.max(DocumentVersion.version_number).label("max_version"),
            )
            .filter(DocumentVersion.document_id.in_(document_ids))
            .group_by(DocumentVersion.document_id)
            .subquery()
        )
        latest_versions = (
            db.query(DocumentVersion)
            .join(
                latest_version_sq,
                and_(
                    DocumentVersion.document_id == latest_version_sq.c.document_id,
                    DocumentVersion.version_number == latest_version_sq.c.max_version,
                ),
            )
            .all()
        )
        latest_by_doc = {version.document_id: version for version in latest_versions}

        chunk_count_rows = (
            db.query(
                DocumentVersion.document_id,
                func.count(Chunk.id),
            )
            .join(Chunk, Chunk.document_version_id == DocumentVersion.id)
            .filter(DocumentVersion.document_id.in_(document_ids))
            .group_by(DocumentVersion.document_id)
            .all()
        )
        chunk_counts = {doc_id: count for doc_id, count in chunk_count_rows}

    documents = [
        DocumentSummary(
            id=doc.id,
            original_name=doc.original_name,
            lifecycle_state=doc.lifecycle_state,
            version_count=count,
            created_at=doc.created_at,
            participation_state=doc.participation_state,
            retrieval_eligible=doc.retrieval_eligible,
            generation_eligible=doc.generation_eligible,
            extraction_method=latest_by_doc[doc.id].extraction_method
            if doc.id in latest_by_doc
            else None,
            integrity_status=latest_by_doc[doc.id].integrity_status
            if doc.id in latest_by_doc
            else None,
            evidence_excerpt_count=chunk_counts.get(doc.id, 0),
        )
        for doc, count in rows
    ]
    return CaseDocumentList(case_id=case_id, documents=documents)
