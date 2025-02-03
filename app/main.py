from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import boto3
from .database import get_db, Base, engine
from .models import Document
from .config import settings
import uuid
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve index.html at root
@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

class DocumentSchema(BaseModel):
    id: str
    filename: str
    s3_url: str
    case_id: str
    visa_type: str
    category: str
    uploaded_at: datetime
    extracted_text: Optional[str] = None

    class Config:
        from_attributes = True

Base.metadata.create_all(bind=engine)

s3_client = boto3.client(
    "s3",
    region_name="us-east-2",
    aws_access_key_id=settings.AWS_ACCESS_KEY,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)

def upload_to_s3(file: UploadFile, case_id: str, visa_type: str, category: str):
    try:
        print(f"Starting S3 upload process...")
        print(f"Case ID: {case_id}")
        print(f"Visa Type: {visa_type}")
        print(f"Category: {category}")
        
        file_id = str(uuid.uuid4())
        s3_key = f"raw/{case_id}/{visa_type}/{category}/{file_id}_{file.filename}"
        
        print(f"S3 Key: {s3_key}")
        
        file.file.seek(0)
        s3_client.upload_fileobj(file.file, settings.S3_BUCKET_NAME, s3_key)
        
        s3_url = f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        print(f"File uploaded successfully to: {s3_url}")
        
        return s3_url
    except Exception as e:
        print(f"S3 Upload Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"S3 Upload Error: {str(e)}")

@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    case_id: str = Form(...),
    visa_type: str = Form(...),
    category: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        print(f"Processing upload for case: {case_id}")
        
        s3_url = upload_to_s3(file, case_id, visa_type, category)
        
        document = Document(
            filename=file.filename,
            s3_url=s3_url,
            case_id=case_id,
            visa_type=visa_type,
            category=category
        )
        
        db.add(document)
        db.commit()
        
        return {
            "status": "success",
            "message": f"File uploaded successfully for case {case_id}",
            "file_url": s3_url
        }
    except Exception as e:
        print(f"Upload Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/")
async def get_documents(
    db: Session = Depends(get_db),
    case_id: Optional[str] = None,
    visa_type: Optional[str] = None
):
    query = db.query(Document)
    if case_id:
        query = query.filter(Document.case_id == case_id)
    if visa_type:
        query = query.filter(Document.visa_type == visa_type)
    return query.order_by(Document.uploaded_at.desc()).all()

@app.get("/categories/{visa_type}")
async def get_categories(visa_type: str):
    if visa_type == "EB1":
        return {
            "categories": [
                "A. Evidence of receipt of lesser nationally or internationally recognized prizes or awards for excellence",
                "B. Evidence of membership in associations in the field which demand outstanding achievement",
                "C. Evidence of published material about the applicant",
                "D. Evidence that the applicant has been asked to judge the work of others",
                "E. Evidence of the applicant's original scientific, scholarly contributions",
                "F. Evidence of the applicant's authorship of scholarly articles",
                "G. Evidence that the applicant's work has been displayed",
                "H. Evidence of the applicant's performance of a leading or critical role",
                "I. Evidence that the applicant commands a high salary",
                "J. Evidence of the applicant's commercial successes",
                "Letters of Support",
                "Professional Plan"
            ]
        }
    elif visa_type == "EB2":
        return {
            "categories": [
                "01_General_Documents",
                "02_Applicant_Background",
                "03_NIW_Criterion_1_Significant_Merit_and_Importance",
                "04_NIW_Criterion_2_Positioned_to_Advance_the_Field",
                "05_NIW_Criterion_3_Benefit_to_USA_Without_Labor_Certification",
                "06_Letters_of_Recommendation",
                "07_Peer_Reviewed_Publications",
                "08_Additional_Supporting_Documents"
            ]
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid visa type")
    
@app.get("/cases/")
async def get_cases(db: Session = Depends(get_db)):
    # Fetch all documents, ordered by upload date (most recent first)
    documents = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    
    # Group documents by case_id
    cases_map = {}
    for doc in documents:
        if doc.case_id not in cases_map:
            cases_map[doc.case_id] = {
                "case_id": doc.case_id,
                "visa_types": set(),
                "files": []
            }
        cases_map[doc.case_id]["visa_types"].add(doc.visa_type)
        cases_map[doc.case_id]["files"].append({
            "id": doc.id,
            "filename": doc.filename,
            "s3_url": doc.s3_url,
            "category": doc.category,
            "uploaded_at": doc.uploaded_at
        })
    
    # Convert the visa_types set to a list for each case
    cases = []
    for case in cases_map.values():
        case["visa_types"] = list(case["visa_types"])
        cases.append(case)
    
    return cases
