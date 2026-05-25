"""Case-level endpoints.

POST /cases
GET  /cases/{case_id}/documents
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Case, Document, DocumentVersion
from app.core.schemas import (
    CaseCreate,
    CaseDocumentList,
    CaseResponse,
    DocumentSummary,
)


router = APIRouter(tags=["cases"])


@router.post("/cases", response_model=CaseResponse, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)) -> CaseResponse:
    case = Case(case_ref=payload.case_ref, visa_type=payload.visa_type)
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
    case_id: str, db: Session = Depends(get_db)
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

    documents = [
        DocumentSummary(
            id=doc.id,
            original_name=doc.original_name,
            lifecycle_state=doc.lifecycle_state,
            version_count=count,
            created_at=doc.created_at,
        )
        for doc, count in rows
    ]
    return CaseDocumentList(case_id=case_id, documents=documents)
