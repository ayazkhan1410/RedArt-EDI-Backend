"""MinIO / S3 upload helper (boto3)."""

from __future__ import annotations

import logging

import boto3
from botocore.client import Config
from django.conf import settings

logger = logging.getLogger(__name__)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None) or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket(bucket=None):
    """
    Verify or create bucket.  In local/docker (DEBUG) auto-creates via MinIO.
    In production: bucket must exist; logs a warning rather than hard-raising so
    that a missing S3 config never blocks the SFTP upload path (S3 = audit only).
    Returns bucket name or None if unavailable.
    """
    bucket = bucket or settings.AWS_STORAGE_BUCKET_NAME
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
        return bucket
    except Exception as exc:
        if settings.DEBUG:
            try:
                client.create_bucket(Bucket=bucket)
                logger.info("Created S3/MinIO bucket=%s", bucket)
                return bucket
            except Exception:
                logger.exception("ensure_bucket failed for %s", bucket)
                return None
        # Production: log and return None — SFTP is the critical path.
        logger.warning(
            "S3 audit bucket '%s' not accessible (%s). "
            "Set AWS_* env vars and create the private bucket. "
            "SFTP upload is unaffected.",
            bucket,
            exc,
        )
        return None


def upload_bytes_to_s3(*, key, data: bytes, content_type="text/plain", bucket=None) -> str | None:
    """
    Upload to S3/MinIO for audit archiving.  Returns s3:// URI or None on failure.
    Never raises — S3 is audit-only; SFTP is the authoritative delivery channel.
    """
    try:
        resolved = ensure_bucket(bucket)
        if resolved is None:
            return None
        client = get_s3_client()
        client.put_object(
            Bucket=resolved,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",  # enforce encryption at rest
        )
        uri = f"s3://{resolved}/{key}"
        logger.info("S3 audit upload ok uri=%s bytes=%s", uri, len(data))
        return uri
    except Exception as exc:
        logger.warning("S3 audit upload failed (non-fatal) key=%s: %s", key, exc)
        return None
