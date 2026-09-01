"""Claim document blob storage (MinIO/S3 primary, local MEDIA fallback)."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def allowed_claim_document_content_types() -> frozenset[str]:
    return frozenset(
        getattr(
            settings,
            "CLAIM_DOCUMENT_ALLOWED_CONTENT_TYPES",
            ("application/pdf", "image/jpeg", "image/png"),
        )
    )


def max_claim_document_bytes() -> int:
    return int(getattr(settings, "CLAIM_DOCUMENT_MAX_BYTES", 10 * 1024 * 1024))


def compute_bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_document_filename(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return "document.bin"
    base = Path(raw).name
    safe = _FILENAME_SAFE.sub("_", base).strip("._")
    return safe or "document.bin"


def validate_upload_payload(
    data: bytes,
    content_type: str | None,
) -> str:
    if not data:
        raise ValueError("Uploaded file is empty.")
    max_bytes = max_claim_document_bytes()
    if len(data) > max_bytes:
        raise ValueError(
            f"File exceeds maximum size of {max_bytes} bytes."
        )
    ctype = (content_type or "application/octet-stream").strip().lower()
    allowed = allowed_claim_document_content_types()
    if ctype not in allowed:
        raise ValueError(
            f"Content type '{ctype}' is not allowed. "
            f"Allowed: {', '.join(sorted(allowed))}."
        )
    return ctype


def _reject_unsafe_blob_ref(ref: str) -> str:
    cleaned = (ref or "").strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("Document has no stored file reference.")
    if cleaned.startswith("/") or "://" in cleaned:
        raise ValueError("Invalid blob reference path.")
    parts = [p for p in cleaned.split("/") if p]
    if any(p == ".." for p in parts):
        raise ValueError("Invalid blob reference path.")
    return cleaned


def _resolve_media_path(ref: str) -> Path:
    ref = _reject_unsafe_blob_ref(ref)
    media_root = Path(settings.MEDIA_ROOT).resolve()
    path = (media_root / ref).resolve()
    if media_root not in path.parents and path != media_root:
        raise ValueError("Invalid blob reference path.")
    return path


def _read_bytes_with_limit(stream, max_bytes: int) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = stream.read(min(65536, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"File exceeds maximum size of {max_bytes} bytes.")
        chunks.append(chunk)
    return b"".join(chunks)


def upload_claim_document_bytes(
    *,
    claim_id: int,
    document_type: str,
    file_name: str,
    data: bytes,
    content_type: str | None = None,
) -> dict:
    """
    Store claim document bytes and return storage metadata.
    Raises ValueError on validation failures.
    """
    content_type = validate_upload_payload(data, content_type)
    document_hash = compute_bytes_hash(data)
    safe_name = sanitize_document_filename(file_name)
    key = f"claim-documents/{claim_id}/{document_type}/{safe_name}"

    blob_ref = None
    try:
        from apps.edi.utils.s3_client import upload_bytes_to_s3

        blob_ref = upload_bytes_to_s3(
            key=key,
            data=data,
            content_type=content_type,
        )
    except Exception:
        logger.warning(
            "S3/MinIO upload failed for claim_id=%s; using local MEDIA fallback",
            claim_id,
            exc_info=True,
        )
        rel_dir = f"claim-documents/{claim_id}/{document_type}"
        abs_dir = Path(settings.MEDIA_ROOT) / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        target = abs_dir / safe_name
        target.write_bytes(data)
        blob_ref = f"{rel_dir}/{safe_name}".replace("\\", "/")

    return {
        "blob_ref": blob_ref,
        "document_hash": document_hash,
        "file_size": len(data),
        "content_type": content_type,
        "file_name": safe_name,
    }


def download_claim_document_bytes(blob_ref: str) -> tuple[bytes, str]:
    """Return (bytes, content_type) for a stored document reference."""
    ref = _reject_unsafe_blob_ref(blob_ref)
    max_bytes = max_claim_document_bytes()

    if ref.startswith("s3://"):
        without = ref[len("s3://") :]
        bucket, key = without.split("/", 1)
        from apps.edi.utils.s3_client import get_s3_client

        client = get_s3_client()
        head = client.head_object(Bucket=bucket, Key=key)
        content_length = head.get("ContentLength")
        if content_length is not None and content_length > max_bytes:
            raise ValueError(f"File exceeds maximum size of {max_bytes} bytes.")
        obj = client.get_object(Bucket=bucket, Key=key)
        body = _read_bytes_with_limit(obj["Body"], max_bytes)
        ctype = obj.get("ContentType") or "application/octet-stream"
        return body, ctype

    path = _resolve_media_path(ref)
    if not path.is_file():
        raise ValueError("Stored document file not found.")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"File exceeds maximum size of {max_bytes} bytes.")
    return path.read_bytes(), "application/octet-stream"
