"""Import task error classification for Celery retry policy."""


class PermanentImportError(Exception):
    """Non-retryable import failure (bad data, missing batch, etc.)."""


class RetryableImportError(Exception):
    """Transient failure — Celery may retry."""
