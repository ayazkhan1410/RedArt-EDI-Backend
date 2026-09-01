"""277 SFTP import poll tests."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from apps.core.testing import AuthAPITestCase
from apps.edi.tests import EDIFixturesMixin


class EDI277ImportPollAPITests(EDIFixturesMixin, AuthAPITestCase):
    def test_poll_import_277_async_returns_celery_task(self):
        with patch("apps.edi.import_277_poll_views.poll_edi_277_imports") as mock_poll:
            mock_poll.delay.return_value.id = "task-import-277-1"
            response = self.client.post(
                reverse("edi-277-import-poll"),
                {"async_mode": True},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["data"]["message"], "Importing started.")
        self.assertEqual(response.data["data"]["celery_task_id"], "task-import-277-1")
        mock_poll.delay.assert_called_once()

    def test_process_import_277_parses_and_marks_imported(self):
        from apps.edi.choices import EDI999ImportStatus, SFTPDirectoryPurpose
        from apps.edi.models import EDI277Import, SFTPCredentials, SFTPDirectory
        from apps.edi.utils.import_277_poll import process_edi_277_import

        cred = SFTPCredentials.objects.create(
            name="TEST-SFTP-277",
            trading_partner=self.partner,
            host="sftp.test.local",
            port=22,
            username="user",
            password="secret",
            environment="TEST",
            is_active=True,
        )
        directory = SFTPDirectory.objects.create(
            name="IN-277",
            credentials=cred,
            purpose=SFTPDirectoryPurpose.INBOUND_277,
            sending_path="/send",
            receiving_path="/recv",
            is_active=True,
        )
        content = (
            "ISA*00*          *00*          *ZZ*COMEDASSISTPROG*ZZ*89513013       "
            "*260817*1947*^*00501*000000001*0*T*:~"
            "GS*HN*COMEDASSISTPROG*89513013*20260817*1947*1*X*005010X214~"
            "ST*277*0001*005010X214~"
            "TRN*2*TRACK001~"
            "REF*D9*C-EDI-1~"
            "STC*A2:19:PR~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        row = EDI277Import.objects.create(
            credentials=cred,
            directory=directory,
            batch=self.batch,
            filename="status_277.txt",
            remote_path="/recv/status_277.txt",
            status=EDI999ImportStatus.QUEUED,
            is_active=True,
        )
        with patch(
            "apps.edi.utils.import_277_poll.download_bytes_via_sftp",
            return_value=content.encode("utf-8"),
        ):
            result = process_edi_277_import(row.id, batch_id=self.batch.id)
        self.assertEqual(result["status"], EDI999ImportStatus.IMPORTED)
        self.assertTrue(result.get("acknowledgement_id"))
