"""Text extraction with three-tier PDF fallback (PyPDF2 -> Textract -> OCR) and docx support.

This module never raises. On total failure it returns an `ExtractionResult` with
text="", method=None, status="failed". For unsupported file types it returns
status="skipped".
"""
from dataclasses import dataclass
from io import BytesIO
from typing import Optional
import logging
import os

import boto3
import PyPDF2
import pytesseract
from docx import Document as DocxDocument
from pdf2image import convert_from_bytes


logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")


@dataclass
class ExtractionResult:
    text: str
    method: Optional[str]   # 'pypdf2' | 'textract' | 'ocr' | 'docx' | None
    status: str             # 'completed' | 'failed' | 'skipped'
    page_count: Optional[int]


def extract_text(file_bytes: bytes, original_filename: str) -> ExtractionResult:
    """Extract text from a document. Never raises."""
    try:
        ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""

        if ext == "docx":
            return _extract_docx(file_bytes)
        if ext == "pdf":
            return _extract_pdf(file_bytes)

        return ExtractionResult(text="", method=None, status="skipped", page_count=None)
    except Exception:
        logger.exception("Unexpected error in extract_text")
        return ExtractionResult(text="", method=None, status="failed", page_count=None)


def _extract_docx(file_bytes: bytes) -> ExtractionResult:
    try:
        doc = DocxDocument(BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
        status = "completed" if text.strip() else "failed"
        return ExtractionResult(
            text=text,
            method="docx" if status == "completed" else None,
            status=status,
            page_count=None,
        )
    except Exception:
        logger.exception("docx extraction failed")
        return ExtractionResult(text="", method=None, status="failed", page_count=None)


def _extract_pdf(file_bytes: bytes) -> ExtractionResult:
    text, page_count = _try_pypdf2(file_bytes)
    if text.strip():
        return ExtractionResult(
            text=text, method="pypdf2", status="completed", page_count=page_count
        )

    text = _try_textract(file_bytes)
    if text.strip():
        return ExtractionResult(
            text=text, method="textract", status="completed", page_count=page_count
        )

    text, ocr_pages = _try_ocr(file_bytes)
    if text.strip():
        return ExtractionResult(
            text=text,
            method="ocr",
            status="completed",
            page_count=ocr_pages or page_count,
        )

    return ExtractionResult(text="", method=None, status="failed", page_count=page_count)


def _try_pypdf2(file_bytes: bytes) -> tuple[str, Optional[int]]:
    try:
        reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        pages = len(reader.pages)
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts), pages
    except Exception:
        logger.exception("PyPDF2 extraction failed")
        return "", None


def _try_textract(file_bytes: bytes) -> str:
    try:
        client = boto3.client(
            "textract",
            region_name=AWS_REGION,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
        response = client.detect_document_text(Document={"Bytes": file_bytes})
        lines = [
            block["Text"]
            for block in response.get("Blocks", [])
            if block.get("BlockType") == "LINE"
        ]
        return "\n".join(lines)
    except Exception:
        logger.exception("Textract extraction failed")
        return ""


def _try_ocr(file_bytes: bytes) -> tuple[str, Optional[int]]:
    try:
        images = convert_from_bytes(file_bytes)
        parts: list[str] = []
        for image in images:
            try:
                parts.append(pytesseract.image_to_string(image))
            except Exception:
                continue
        return "\n\n".join(parts), len(images)
    except Exception:
        logger.exception("OCR extraction failed")
        return "", None
