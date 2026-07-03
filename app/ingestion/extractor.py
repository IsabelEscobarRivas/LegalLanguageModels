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
        if ext == "txt":
            return _extract_txt(file_bytes)
        if ext == "pdf":
            return _extract_pdf(file_bytes)

        return ExtractionResult(text="", method=None, status="skipped", page_count=None)
    except Exception:
        logger.exception("Unexpected error in extract_text")
        return ExtractionResult(text="", method=None, status="failed", page_count=None)


MINIMUM_TEXT_DENSITY = 0.05   # chars per byte of raw file
MINIMUM_CONFIDENCE = 0.3      # OCR confidence floor
OCR_CORRUPTION_PATTERNS = [
    r'[^\x00-\x7F]{10,}',     # long non-ASCII runs
    r'(\S)\1{8,}',             # 8+ repeated non-space chars
]


def assess_extraction_integrity(
    result: ExtractionResult,
    file_bytes: bytes,
) -> dict:
    """Assess whether extracted text meets quality thresholds.

    Returns:
      {
        "integrity_status": str,  one of the CHECK values
        "extraction_confidence": float,  0.0–1.0
        "text_density": float,    chars / raw_bytes
        "chunking_eligible": bool
      }

    Never raises.
    """
    import re

    if result.status != "completed" or not result.text.strip():
        return {
            "integrity_status": "failed_low_confidence",
            "extraction_confidence": 0.0,
            "text_density": 0.0,
            "chunking_eligible": False,
        }

    text = result.text
    raw_len = max(len(file_bytes), 1)
    text_density = len(text) / raw_len

    # Corruption check
    for pattern in OCR_CORRUPTION_PATTERNS:
        if re.search(pattern, text):
            return {
                "integrity_status": "failed_corruption",
                "extraction_confidence": 0.1,
                "text_density": text_density,
                "chunking_eligible": False,
            }

    if text_density < MINIMUM_TEXT_DENSITY:
        return {
            "integrity_status": "failed_low_density",
            "extraction_confidence": 0.2,
            "text_density": text_density,
            "chunking_eligible": False,
        }

    # Confidence by method
    method_confidence = {
        "pypdf2": 0.95,
        "docx": 0.98,
        "txt": 1.0,
        "textract": 0.90,
        "ocr": 0.65,
    }
    confidence = method_confidence.get(result.method or "", 0.5)

    if confidence < MINIMUM_CONFIDENCE:
        return {
            "integrity_status": "failed_low_confidence",
            "extraction_confidence": confidence,
            "text_density": text_density,
            "chunking_eligible": False,
        }

    integrity_status = "passed_ocr" if result.method == "ocr" else "passed"

    return {
        "integrity_status": integrity_status,
        "extraction_confidence": confidence,
        "text_density": text_density,
        "chunking_eligible": True,
    }


def _extract_txt(file_bytes: bytes) -> ExtractionResult:
    try:
        text = file_bytes.decode("utf-8", errors="replace").strip()
        status = "completed" if text else "failed"
        return ExtractionResult(
            text=text,
            method="txt" if status == "completed" else None,
            status=status,
            page_count=None,
        )
    except Exception:
        logger.exception("txt extraction failed")
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
        # Assess integrity before committing to PyPDF2 result
        candidate = ExtractionResult(
            text=text,
            method="pypdf2",
            status="completed",
            page_count=page_count,
        )
        integrity = assess_extraction_integrity(candidate, file_bytes)
        if integrity["integrity_status"] != "failed_corruption":
            # PyPDF2 result is good — return it
            return candidate
        # Corruption detected — fall through to OCR
        logger.warning(
            "PyPDF2 text failed corruption check "
            "(text_density=%.3f) — falling through to OCR",
            integrity["text_density"],
        )

    # Textract path (handles missing text, not corrupt text)
    text = _try_textract(file_bytes)
    if text.strip():
        return ExtractionResult(
            text=text,
            method="textract",
            status="completed",
            page_count=page_count
        )

    # OCR path (handles both missing and corrupt text)
    text, ocr_pages = _try_ocr(file_bytes)
    if text.strip():
        return ExtractionResult(
            text=text,
            method="ocr",
            status="completed",
            page_count=ocr_pages or page_count,
        )

    return ExtractionResult(
        text="", method=None, status="failed", page_count=page_count
    )


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
