"""Celery tasks for EDI file transport and inbound 999 import."""

from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from apps.edi.choices import EDI999ImportStatus, EDI835ImportStatus, EDIFileStatus
from apps.edi.models import EDI999Import, EDI835Import
from apps.edi.utils.import_999 import (
    process_edi_999_import,
    queue_edi_999_import_poll,
)
from apps.edi.utils.import_835_poll import (
    process_edi_835_import,
    queue_edi_835_import_poll,
)
from apps.edi.utils.upload import queue_edi_file_upload, run_edi_file_upload

logger = logging.getLogger(__name__)

# First try is immediate (countdown 0). After each failure: 60s, 180s, 360s.
UPLOAD_RETRY_COUNTDOWNS = (60, 180, 360)
IMPORT_999_RETRY_COUNTDOWNS = (60, 180, 360)
IMPORT_835_RETRY_COUNTDOWNS = (60, 180, 360)


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


@shared_task(
    bind=True,
    name="apps.edi.tasks.poll_edi_999_imports",
    acks_late=True,
)
def poll_edi_999_imports(self, credentials_id=None, batch_id=None):
    """
    Hourly (or manual) poller: discover inbound 999 files on SFTP and queue
    process_edi_999_import_task for each new remote path.
    """
    logger.info(
        "Celery poll_edi_999_imports start credentials_id=%s batch_id=%s task=%s",
        credentials_id,
        batch_id,
        self.request.id,
    )
    result = queue_edi_999_import_poll(
        credentials_id=credentials_id,
        batch_id=batch_id,
    )
    logger.info("Celery poll_edi_999_imports done %s", result)
    return result


@shared_task(
    bind=True,
    name="apps.edi.tasks.process_edi_999_import_task",
    max_retries=3,
    acks_late=True,
)
def process_edi_999_import_task(self, import_id, batch_id=None):
    """
    Download one remote 999, parse, create EDIAcknowledgement.
    Retries on hard failures with 60 / 180 / 360s backoff.
    SKIPPED / already IMPORTED outcomes are not retried.
    """
    logger.info(
        "Celery process_edi_999_import start id=%s batch_id=%s task=%s retries=%s",
        import_id,
        batch_id,
        self.request.id,
        self.request.retries,
    )
    try:
        EDI999Import.objects.filter(pk=import_id).update(
            celery_task_id=self.request.id,
            attempt=self.request.retries + 1,
        )
        result = process_edi_999_import(import_id, batch_id=batch_id)
        status_value = result.get("status")
        if status_value in (
            EDI999ImportStatus.IMPORTED,
            EDI999ImportStatus.SKIPPED,
        ):
            logger.info("Celery process_edi_999_import done %s", result)
            return result
        raise RuntimeError(
            f"Import 999 did not complete: status={status_value} "
            f"message={result.get('message')}"
        )
    except MaxRetriesExceededError:
        logger.exception(
            "Celery process_edi_999_import exhausted retries id=%s",
            import_id,
        )
        raise
    except Exception as exc:
        row = EDI999Import.objects.filter(pk=import_id).first()
        if row and row.status == EDI999ImportStatus.SKIPPED:
            return {
                "id": import_id,
                "status": row.status,
                "message": row.message,
            }
        if self.request.retries >= self.max_retries:
            logger.exception(
                "Celery process_edi_999_import giving up id=%s err=%s",
                import_id,
                exc,
            )
            raise

        countdown = IMPORT_999_RETRY_COUNTDOWNS[self.request.retries]
        if row:
            row.status = EDI999ImportStatus.QUEUED
            row.message = (
                f"Auto-retry scheduled in {countdown}s "
                f"(celery retry {self.request.retries + 1}/{self.max_retries})."
            )[:500]
            row.celery_task_id = self.request.id
            row.save(
                update_fields=[
                    "status",
                    "message",
                    "celery_task_id",
                    "updated_at",
                ]
            )

        logger.warning(
            "Celery process_edi_999_import retry id=%s retry=%s/%s countdown=%ss err=%s",
            import_id,
            self.request.retries + 1,
            self.max_retries,
            countdown,
            exc,
        )
        raise self.retry(
            exc=exc,
            countdown=countdown,
            args=(import_id, batch_id),
        )


@shared_task(
    bind=True,
    name="apps.edi.tasks.poll_edi_835_imports",
    acks_late=True,
)
def poll_edi_835_imports(self, credentials_id=None):
    """Hourly (or manual) poller for inbound 835 ERA files on SFTP."""
    logger.info(
        "Celery poll_edi_835_imports start credentials_id=%s task=%s",
        credentials_id,
        self.request.id,
    )
    result = queue_edi_835_import_poll(credentials_id=credentials_id)
    logger.info("Celery poll_edi_835_imports done %s", result)
    return result


@shared_task(
    bind=True,
    name="apps.edi.tasks.process_edi_835_import_task",
    max_retries=3,
    acks_late=True,
)
def process_edi_835_import_task(self, import_id):
    """Download one remote 835, parse, apply PAID/DENIED via remittance import."""
    logger.info(
        "Celery process_edi_835_import start id=%s task=%s retries=%s",
        import_id,
        self.request.id,
        self.request.retries,
    )
    try:
        EDI835Import.objects.filter(pk=import_id).update(
            celery_task_id=self.request.id,
            attempt=self.request.retries + 1,
        )
        result = process_edi_835_import(import_id)
        status_value = result.get("status")
        if status_value in (
            EDI835ImportStatus.IMPORTED,
            EDI835ImportStatus.SKIPPED,
        ):
            logger.info("Celery process_edi_835_import done %s", result)
            return result
        raise RuntimeError(
            f"Import 835 did not complete: status={status_value} "
            f"message={result.get('message')}"
        )
    except MaxRetriesExceededError:
        logger.exception(
            "Celery process_edi_835_import exhausted retries id=%s",
            import_id,
        )
        raise
    except Exception as exc:
        row = EDI835Import.objects.filter(pk=import_id).first()
        if row and row.status == EDI835ImportStatus.SKIPPED:
            return {
                "id": import_id,
                "status": row.status,
                "message": row.message,
            }
        if self.request.retries >= self.max_retries:
            logger.exception(
                "Celery process_edi_835_import giving up id=%s err=%s",
                import_id,
                exc,
            )
            raise

        countdown = IMPORT_835_RETRY_COUNTDOWNS[self.request.retries]
        if row:
            row.status = EDI835ImportStatus.QUEUED
            row.message = (
                f"Auto-retry scheduled in {countdown}s "
                f"(celery retry {self.request.retries + 1}/{self.max_retries})."
            )[:500]
            row.celery_task_id = self.request.id
            row.save(
                update_fields=[
                    "status",
                    "message",
                    "celery_task_id",
                    "updated_at",
                ]
            )

        logger.warning(
            "Celery process_edi_835_import retry id=%s retry=%s/%s countdown=%ss err=%s",
            import_id,
            self.request.retries + 1,
            self.max_retries,
            countdown,
            exc,
        )
        raise self.retry(exc=exc, countdown=countdown, args=(import_id,))
