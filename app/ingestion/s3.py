"""S3 upload helpers for raw documents and extracted text.

Key formats are strict and defined in one place:
  raw       -> raw/{case_uuid}/{document_uuid}/{NNN}/{original_filename}
  extracted -> extracted/{case_uuid}/{document_uuid}/{NNN}/extracted.txt
where {NNN} is `version_number` zero-padded to three digits.

S3 credentials are never returned from or logged by these functions.
"""
import os

import boto3


AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")


def _s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def _bucket() -> str:
    bucket = os.environ.get("S3_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME is not configured")
    return bucket


def raw_key(case_id: str, document_id: str, version_number: int, original_filename: str) -> str:
    return f"raw/{case_id}/{document_id}/{version_number:03d}/{original_filename}"


def extracted_key(case_id: str, document_id: str, version_number: int) -> str:
    return f"extracted/{case_id}/{document_id}/{version_number:03d}/extracted.txt"


def upload_raw_file(
    file_bytes: bytes,
    case_id: str,
    document_id: str,
    version_number: int,
    original_filename: str,
    content_type: str | None = None,
) -> str:
    """Upload a raw document to S3. Returns the S3 key."""
    key = raw_key(case_id, document_id, version_number, original_filename)
    extra: dict = {}
    if content_type:
        extra["ContentType"] = content_type
    _s3_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=file_bytes,
        **extra,
    )
    return key


def upload_extracted_text(
    text: str,
    case_id: str,
    document_id: str,
    version_number: int,
) -> str:
    """Upload extracted text as UTF-8 to S3. Returns the S3 key."""
    key = extracted_key(case_id, document_id, version_number)
    _s3_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    return key
