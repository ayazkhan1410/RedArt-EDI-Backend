"""Secret encryption helpers for SFTP credentials at rest."""

from __future__ import annotations

import base64
import hashlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_PREFIX = "fernet:"


def _fernet():
    """Derive a Fernet key from DJANGO_SECRET_KEY (stable across restarts)."""
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str | None) -> str | None:
    if value in (None, ""):
        return value
    text = str(value)
    if text.startswith(_PREFIX):
        return text
    token = _fernet().encrypt(text.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt if prefixed; otherwise return plaintext (legacy rows)."""
    if value in (None, ""):
        return value
    text = str(value)
    if not text.startswith(_PREFIX):
        return text
    raw = text[len(_PREFIX) :]
    try:
        return _fernet().decrypt(raw.encode("ascii")).decode("utf-8")
    except Exception:
        logger.exception("Failed to decrypt secret field")
        raise ValueError("Unable to decrypt stored secret.")


def secret_is_set(value: str | None) -> bool:
    return bool(value and str(value).strip())
