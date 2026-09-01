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
    bucket = bucket or settings.AWS_STORAGE_BUCKET_NAME
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception as exc:
        if not settings.DEBUG:
            raise ValueError(
                f"S3 bucket '{bucket}' is not accessible. "
                "Create the bucket during infrastructure setup."
            ) from exc
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("Created S3/MinIO bucket=%s", bucket)
        except Exception:
            logger.exception("ensure_bucket failed for %s", bucket)
            raise
    return bucket


def upload_bytes_to_s3(*, key, data: bytes, content_type="text/plain", bucket=None) -> str:
    bucket = ensure_bucket(bucket)
    client = get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    uri = f"s3://{bucket}/{key}"
    logger.info("S3/MinIO upload ok uri=%s bytes=%s", uri, len(data))
    return uri
