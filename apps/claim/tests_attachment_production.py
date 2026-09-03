"""Production attachment adapter, bulk review, and document date fields."""

from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from apps.claim.choices import (
    AttachmentSubmissionStatus,
    ClaimStatus,
    DocumentType,
)
from apps.claim.models import AttachmentSubmission
from apps.claim.tests_attachment_workflow import AttachmentWorkflowAPITests
from apps.claim.utils.attachment_adapter import MftAttachmentAdapter, get_attachment_adapter
from apps.claim.utils.attachment_service import submit_claim_attachments
from apps.claim_service_line.models import ClaimServiceLine
from apps.edi.choices import SFTPDirectoryPurpose
from apps.edi.models import SFTPCredentials, SFTPDirectory
from apps.trading_partner.models import TradingPartner


class ProductionMftAdapterTests(AttachmentWorkflowAPITests):
    def setUp(self):
        super().setUp()
        self.partner = TradingPartner.objects.create(
            name="Test Transport LLC",
            sender_id="SMPLSENDER1",
            receiver_id="COMEDASSISTPROG",
            environment="PRODUCTION",
        )
        if not ClaimServiceLine.objects.filter(claim=self.claim, is_active=True).exists():
            ClaimServiceLine.objects.create(
                claim=self.claim,
                procedure_code="A0120",
                from_date=self.trip.service_date,
                to_date=self.trip.service_date,
                units=self.trip.mileage_units,
                mileage=self.trip.one_way_miles,
                charge=self.trip.charge,
                is_active=True,
            )
        self.patient.gender = "M"
        self.patient.address_line_1 = "100 Main St"
        self.patient.city = "Denver"
        self.patient.state = "CO"
        self.patient.zip = "80202"
        self.patient.phone = "3035550100"
        self.patient.save(
            update_fields=[
                "gender",
                "address_line_1",
                "city",
                "state",
                "zip",
                "phone",
                "updated_at",
            ]
        )
        self.provider.taxonomy_code = "343900000X"
        self.provider.address_line_1 = "100 Main St"
        self.provider.city = "Denver"
        self.provider.state = "CO"
        self.provider.zip = "80202"
        self.provider.phone = "3035550199"
        self.provider.save(
            update_fields=[
                "taxonomy_code",
                "address_line_1",
                "city",
                "state",
                "zip",
                "phone",
                "updated_at",
            ]
        )

    @override_settings(
        ATTACHMENT_MFT_ENABLED=True,
        ATTACHMENT_PRODUCTION_MODE=True,
        ATTACHMENT_PRODUCTION_DEFAULT_CHANNEL="HCPF_APPROVED_CHANNEL",
        ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE="{claim_number}/{document_type}/{filename}",
    )
    def test_production_mode_defaults_to_mft_channel(self):
        adapter = get_attachment_adapter(channel=None)
        self.assertEqual(adapter.channel, "HCPF_APPROVED_CHANNEL")

    @override_settings(ATTACHMENT_MFT_ENABLED=True, ATTACHMENT_PRODUCTION_MODE=True)
    def test_production_requires_outbound_attachment_directory(self):
        creds = SFTPCredentials.objects.create(
            name="GEN-ONLY",
            host="sftp.test.local",
            port=22,
            username="user",
            password="secret",
            environment="PRODUCTION",
            is_active=True,
        )
        SFTPDirectory.objects.create(
            name="GEN",
            credentials=creds,
            purpose=SFTPDirectoryPurpose.GENERAL,
            sending_path="/general",
            receiving_path="/recv",
            is_active=True,
        )
        adapter = MftAttachmentAdapter()
        with self.assertRaises(ValueError) as ctx:
            adapter.transmit(self.claim, [], environment="PRODUCTION")
        self.assertIn("OUTBOUND_ATTACHMENT", str(ctx.exception))

    @override_settings(
        ATTACHMENT_MFT_ENABLED=True,
        ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE="{claim_number}/{document_type}/{filename}",
    )
    @patch(
        "apps.claim.utils.document_storage.download_claim_document_bytes",
        return_value=(b"%PDF-1.4 test", "application/pdf"),
    )
    @patch("apps.claim.utils.attachment_adapter.upload_bytes_via_sftp", return_value="/out/file.pdf")
    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_mft_upload_uses_path_template(self, _mock_s3, mock_sftp, _mock_download):
        creds = SFTPCredentials.objects.create(
            name="ATTACH-OUT",
            host="sftp.test.local",
            port=22,
            username="user",
            password="secret",
            environment="TEST",
            is_active=True,
        )
        SFTPDirectory.objects.create(
            name="ATTACH-OUT",
            credentials=creds,
            purpose=SFTPDirectoryPurpose.OUTBOUND_ATTACHMENT,
            sending_path="/attachments",
            receiving_path="/attachments-recv",
            is_active=True,
        )
        self._complete_documents()
        submission = submit_claim_attachments(
            self.claim.id,
            channel="HCPF_APPROVED_CHANNEL",
            environment="TEST",
        )
        self.assertEqual(submission.status, AttachmentSubmissionStatus.SUBMITTED)
        mock_sftp.assert_called()
        call_kwargs = mock_sftp.call_args.kwargs
        self.assertIn(self.claim.claim_number, call_kwargs.get("filename", ""))


class BulkAttachmentReviewAPITests(AttachmentWorkflowAPITests):
    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_bulk_review_submit_and_confirm(self, _mock_s3):
        self._complete_documents()
        response = self.client.post(
            reverse("attachment-submission-bulk-review"),
            {
                "items": [
                    {
                        "claim_id": self.claim.id,
                        "action": "SUBMIT",
                        "channel": "HCPF_PORTAL",
                        "submission_reference": "BULK-REF-1",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["success_count"], 1)
        submission = AttachmentSubmission.objects.filter(claim=self.claim).first()
        self.assertEqual(submission.status, AttachmentSubmissionStatus.SUBMITTED)

        confirm = self.client.post(
            reverse("attachment-submission-bulk-review"),
            {
                "items": [
                    {
                        "claim_id": self.claim.id,
                        "action": "CONFIRM",
                        "submission_reference": "BULK-CONF-1",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.status, AttachmentSubmissionStatus.CONFIRMED)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.ATTACHMENT_CONFIRMED)


class DocumentDateFieldTests(AttachmentWorkflowAPITests):
    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_upload_accepts_service_and_verification_dates(self, _mock_s3):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.claim.models import ClaimDocument

        log_file = SimpleUploadedFile(
            "trip.pdf", b"%PDF-1.4 test", content_type="application/pdf"
        )
        log = self.client.post(
            reverse("claim-document-upload"),
            {
                "claim": self.claim.id,
                "document_type": "STANDARD_TRIP_LOG",
                "file": log_file,
                "is_signed": True,
                "service_date": "2026-08-30",
            },
            format="multipart",
        )
        self.assertEqual(log.status_code, status.HTTP_201_CREATED)
        log_doc = ClaimDocument.objects.get(pk=log.data["data"]["id"])
        self.assertEqual(str(log_doc.service_date), "2026-08-30")

        ver_file = SimpleUploadedFile(
            "verify.pdf", b"%PDF-1.4 test", content_type="application/pdf"
        )
        ver = self.client.post(
            reverse("claim-document-upload"),
            {
                "claim": self.claim.id,
                "document_type": "MILE_25_VERIFICATION",
                "file": ver_file,
                "is_signed": True,
                "verification_date": "2026-08-30",
            },
            format="multipart",
        )
        self.assertEqual(ver.status_code, status.HTTP_201_CREATED)
        ver_doc = ClaimDocument.objects.get(pk=ver.data["data"]["id"])
        self.assertEqual(str(ver_doc.verification_date), "2026-08-30")
