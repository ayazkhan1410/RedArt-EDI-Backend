"""Generate sample 837P and upload once to HCPF MFT (sync, no Celery)."""

from apps.claim.models import SubmissionBatch
from apps.edi.models import SFTPCredentials
from apps.edi.utils.handler import Generate837PHandler
from apps.edi.utils.upload import queue_edi_file_upload, run_edi_file_upload


def main():
    batch = SubmissionBatch.objects.get(batch_number="REDART-SAMPLE-837P", is_active=True)
    cred = SFTPCredentials.objects.get(name="HCPF-MFT-EDIFECS", environment="TEST", is_active=True)
    print("batch_id", batch.id, "credentials_id", cred.id)

    edi, path, segments = Generate837PHandler(batch.id).generate()
    print("generated", edi.id, edi.filename, "segments", segments, "path", path)

    edi2, attempt, sftp_log, s3_log = queue_edi_file_upload(
        edi_file_id=edi.id,
        credentials_id=cred.id,
    )
    print("queued attempt", attempt, "sftp_log", sftp_log.id, "s3_log", s3_log.id)

    result = run_edi_file_upload(
        edi_file_id=edi2.id,
        attempt=attempt,
        task_id="manual-upload-test",
        credentials_id=cred.id,
    )
    print("result", result)
    sftp_log.refresh_from_db()
    s3_log.refresh_from_db()
    print("sftp_status", sftp_log.status, "msg", (sftp_log.message or "")[:200])
    print("s3_status", s3_log.status, "msg", (s3_log.message or "")[:200])
    print("DONE")


if __name__ == "__main__":
    main()
