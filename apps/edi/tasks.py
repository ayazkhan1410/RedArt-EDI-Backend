"""Celery tasks for EDI file transport."""

from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from apps.edi.choices import EDIFileStatus
from apps.edi.utils.upload import queue_edi_file_upload, run_edi_file_upload

logger = logging.getLogger(__name__)

# First try is immediate (countdown 0). After each failure: 60s, 180s, 360s.
UPLOAD_RETRY_COUNTDOWNS = (60, 180, 360)


@shared_task(
    bind=True,
    name="apps.edi.tasks.upload_edi_file",
    max_retries=3,
    acks_late=True,
)
def upload_edi_file(self, edi_file_id, attempt, credentials_id=None):
    """
    Upload EDI file to SFTP + MinIO.
    On failure: retry up to 3 times with countdowns 60 / 180 / 360 seconds.
    Each retry opens a new transfer-log attempt for FE tracking.
    """
    logger.info(
        "Celery upload_edi_file start id=%s attempt=%s task=%s retries=%s",
        edi_file_id,
        attempt,
        self.request.id,
        self.request.retries,
    )
    try:
        result = run_edi_file_upload(
            edi_file_id=edi_file_id,
            attempt=attempt,
            task_id=self.request.id,
            credentials_id=credentials_id,
        )
        if result.get("status") == EDIFileStatus.UPLOADED:
            logger.info("Celery upload_edi_file success %s", result)
            return result

        raise RuntimeError(
            "Upload did not complete successfully: "
            f"sftp_ok={result.get('sftp_ok')} s3_ok={result.get('s3_ok')}"
        )
    except MaxRetriesExceededError:
        logger.exception(
            "Celery upload_edi_file exhausted retries id=%s attempt=%s",
            edi_file_id,
            attempt,
        )
        raise
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.exception(
                "Celery upload_edi_file giving up id=%s attempt=%s err=%s",
                edi_file_id,
                attempt,
                exc,
            )
            raise

        countdown = UPLOAD_RETRY_COUNTDOWNS[self.request.retries]
        _, next_attempt, sftp_log, s3_log = queue_edi_file_upload(
            edi_file_id=edi_file_id,
            credentials_id=credentials_id,
        )
        for log in (sftp_log, s3_log):
            log.celery_task_id = self.request.id
            log.message = (
                f"Auto-retry scheduled in {countdown}s "
                f"(celery retry {self.request.retries + 1}/{self.max_retries})."
            )[:500]
            log.save(update_fields=["celery_task_id", "message", "updated_at"])

        logger.warning(
            "Celery upload_edi_file scheduling retry id=%s "
            "retry=%s/%s countdown=%ss next_attempt=%s err=%s",
            edi_file_id,
            self.request.retries + 1,
            self.max_retries,
            countdown,
            next_attempt,
            exc,
        )
        raise self.retry(
            exc=exc,
            countdown=countdown,
            args=(edi_file_id, next_attempt, credentials_id),
        )
