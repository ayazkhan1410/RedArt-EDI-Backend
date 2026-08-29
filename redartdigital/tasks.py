"""Celery tasks for the EDI microservice."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _redis_from_url(url: str):
    import redis

    parsed = urlparse(url)
    db = 0
    if parsed.path and parsed.path.strip("/"):
        db = int(parsed.path.strip("/").split("/")[0])

    return redis.Redis(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        db=db,
        password=parsed.password,
        socket_connect_timeout=5,
    )


@shared_task(name="redartdigital.tasks.cleanup_celery_storage")
def cleanup_celery_storage() -> dict:
    """
    Clear Celery result storage in Redis every 24 hours.

    Broker DB (pending queue) is left untouched so in-flight work is safe.
    Only the result backend Redis DB is flushed.
    """
    result_url = settings.CELERY_RESULT_BACKEND
    client = _redis_from_url(result_url)
    keys_before = client.dbsize()
    client.flushdb()
    keys_after = client.dbsize()

    summary = {
        "result_backend": result_url,
        "keys_before": keys_before,
        "keys_after": keys_after,
        "action": "flushdb_result_backend",
    }
    logger.info("Celery storage cleanup complete: %s", summary)
    return summary
