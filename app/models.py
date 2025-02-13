from sqlalchemy import Column, String, DateTime, Text, JSON
from datetime import datetime
import uuid
from .database import Base

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, index=True)
    s3_url = Column(String)
    case_id = Column(String, index=True)
    visa_type = Column(String, index=True)
    category = Column(String, index=True)
    extracted_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    document_metadata = Column(JSON, nullable=True)  # Changed from metadata to document_metadata