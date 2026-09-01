"""Attachment workflow: upload, queue, dashboard, duplicate guard, adapters."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status

from apps.claim.choices import (
    AttachmentStatus,
    AttachmentSubmissionStatus,
    ClaimStatus,
    DocumentStatus,
    DocumentType,
)
from apps.claim.models import AttachmentSubmission, Claim, ClaimDocument
from apps.claim.utils.attachment_service import (
    compute_claim_document_payload_hash,
    submit_claim_attachments,
)
from apps.claim.utils.service import create_claim_from_trip
from apps.core.testing import AuthAPITestCase
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile


class AttachmentWorkflowFixturesMixin:
    def setUp(self):
        super().setUp()
        LongDistanceRule.objects.update_or_create(
            county_type="STANDARD",
            defaults={
                "review_threshold": 52,
                "verification_threshold": 25,
                "is_active": True,
            },
        )
        self.patient = Patient.objects.create(
            first_name="Ali",
            last_name="Khan",
            date_of_birth=date(1995, 5, 12),
            medicaid_member_id="M123456789",
            county="Denver",
        )
        self.provider = ProviderBillingProfile.objects.create(
            legal_name="Al Shifa Bus Service LLC",
            billing_name="Al Shifa Transportation",
            npi="1234567890",
        )
        self.trip = NemtTrip.objects.create(
            patient=self.patient,
            provider=self.provider,
            service_date=date(2026, 8, 30),
            pickup="Ali Home",
            dropoff="Rural Clinic",
            one_way_miles=Decimal("78.00"),
            mileage_units=78,
            charge=Decimal("150.00"),
        )
        self.claim, _ = create_claim_from_trip(
            trip_id=self.trip.id,
            claim_number="C-ATT-001",
            create_service_line=False,
        )


class DocumentStorageTests(AttachmentWorkflowFixturesMixin, TestCase):
    def test_compute_payload_hash_stable(self):
        ClaimDocument.objects.create(
            claim=self.claim,
            document_type=DocumentType.STANDARD_TRIP_LOG,
            document_hash="hash-a",
            blob_ref="claim-documents/1/log.pdf",
            status=DocumentStatus.COMPLETE,
            is_signed=True,
            is_active=True,
        )
        ClaimDocument.objects.create(
            claim=self.claim,
            document_type=DocumentType.MILE_25_VERIFICATION,
            document_hash="hash-b",
            blob_ref="claim-documents/1/ver.pdf",
            status=DocumentStatus.COMPLETE,
            is_signed=True,
            is_active=True,
        )
        h1 = compute_claim_document_payload_hash(self.claim.id)
        h2 = compute_claim_document_payload_hash(self.claim.id)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)


class AttachmentWorkflowAPITests(AttachmentWorkflowFixturesMixin, AuthAPITestCase):
    def _upload_pdf(self, document_type, name="trip.pdf", content=b"%PDF-1.4 test"):
        file = SimpleUploadedFile(name, content, content_type="application/pdf")
        return self.client.post(
            reverse("claim-document-upload"),
            {
                "claim": self.claim.id,
                "document_type": document_type,
                "file": file,
                "is_signed": True,
            },
            format="multipart",
        )

    def _complete_documents(self):
        log = self._upload_pdf("STANDARD_TRIP_LOG", "trip_log.pdf")
        self.assertEqual(log.status_code, status.HTTP_201_CREATED)
        ver = self._upload_pdf("MILE_25_VERIFICATION", "verify.pdf")
        self.assertEqual(ver.status_code, status.HTTP_201_CREATED)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.READY_FOR_837P)

    @patch(
        "apps.claim.workflow_views.download_claim_document_bytes",
        return_value=(b"%PDF-1.4 test", "application/pdf"),
    )
    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/claim-documents/1/log.pdf")
    def test_upload_and_download_document(self, _mock_s3, _mock_download):
        response = self._upload_pdf("STANDARD_TRIP_LOG")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        doc_id = response.data["data"]["id"]
        doc = ClaimDocument.objects.get(pk=doc_id)
        self.assertTrue(doc.blob_ref)
        self.assertTrue(doc.document_hash)
        self.assertEqual(doc.file_size, len(b"%PDF-1.4 test"))

        download = self.client.get(reverse("claim-document-file", kwargs={"pk": doc_id}))
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertIn(b"%PDF", download.content)

    def test_upload_rejects_invalid_content_type(self):
        file = SimpleUploadedFile("bad.exe", b"data", content_type="application/octet-stream")
        response = self.client.post(
            reverse("claim-document-upload"),
            {
                "claim": self.claim.id,
                "document_type": "STANDARD_TRIP_LOG",
                "file": file,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_attachment_queue_lists_missing_docs(self, _mock_s3):
        self._upload_pdf("STANDARD_TRIP_LOG")
        queue = self.client.get(reverse("claim-attachment-queue"))
        self.assertEqual(queue.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(queue.data["count"], 1)
        row = next(r for r in queue.data["data"] if r["claim_id"] == self.claim.id)
        self.assertIn("MILE_25_VERIFICATION", row["missing_types"])
        self.assertFalse(row["documents_complete"])

        filtered = self.client.get(
            reverse("claim-attachment-queue"),
            {"documents_complete": "false"},
        )
        self.assertTrue(
            all(not r["documents_complete"] for r in filtered.data["data"])
        )

    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_attachment_dashboard_counts(self, _mock_s3):
        self._upload_pdf("STANDARD_TRIP_LOG")
        dashboard = self.client.get(reverse("claim-attachment-dashboard"))
        self.assertEqual(dashboard.status_code, status.HTTP_200_OK)
        data = dashboard.data["data"]
        self.assertGreaterEqual(data["long_distance_claims"], 1)
        self.assertGreaterEqual(data["missing_verification"], 1)
        self.assertEqual(data["ready_with_documents"], 0)

    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_duplicate_submission_blocked(self, _mock_s3):
        self._complete_documents()
        first = self.client.post(
            reverse("attachment-submission-submit"),
            {"claim_id": self.claim.id, "channel": "HCPF_PORTAL"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            reverse("attachment-submission-submit"),
            {"claim_id": self.claim.id, "channel": "HCPF_PORTAL"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Duplicate", second.data["message"])

    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_manual_attachment_submission_duplicate_blocked(self, _mock_s3):
        self._complete_documents()
        payload = {
            "claim": self.claim.id,
            "channel": "HCPF_PORTAL",
            "submission_reference": "PORTAL-REF-1",
        }
        first = self.client.post(
            reverse("attachment-submission-list-create"),
            payload,
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            reverse("attachment-submission-list-create"),
            payload,
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_portal_submit_without_reference_queues(self, _mock_s3):
        self._complete_documents()
        response = self.client.post(
            reverse("attachment-submission-submit"),
            {"claim_id": self.claim.id, "channel": "HCPF_PORTAL"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["status"], AttachmentSubmissionStatus.QUEUED)

    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_portal_submit_with_reference_submitted(self, _mock_s3):
        self._complete_documents()
        response = self.client.post(
            reverse("attachment-submission-submit"),
            {
                "claim_id": self.claim.id,
                "channel": "HCPF_PORTAL",
                "submission_reference": "PORTAL-999",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["data"]["status"], AttachmentSubmissionStatus.SUBMITTED
        )
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.attachment_status, AttachmentStatus.SUBMITTED)

    @override_settings(ATTACHMENT_MFT_ENABLED=False)
    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_mft_adapter_disabled_queues(self, _mock_s3):
        self._complete_documents()
        submission = submit_claim_attachments(
            self.claim.id,
            channel="HCPF_APPROVED_CHANNEL",
        )
        self.assertEqual(submission.status, AttachmentSubmissionStatus.QUEUED)
        self.assertIn("disabled", (submission.notes or "").lower())

    @override_settings(ATTACHMENT_MFT_ENABLED=True)
    @patch(
        "apps.claim.utils.document_storage.download_claim_document_bytes",
        return_value=(b"%PDF-1.4 test", "application/pdf"),
    )
    @patch("apps.claim.utils.attachment_adapter.upload_bytes_via_sftp", return_value="/send/C001_log.pdf")
    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_mft_adapter_uploads_when_enabled(self, _mock_s3, _mock_sftp, _mock_download):
        from apps.edi.choices import SFTPDirectoryPurpose
        from apps.edi.models import SFTPCredentials, SFTPDirectory

        creds = SFTPCredentials.objects.create(
            name="ATTACH-SFTP",
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
        self.assertTrue(submission.remote_path)
        _mock_sftp.assert_called()

    @patch("apps.edi.utils.s3_client.upload_bytes_to_s3", return_value="s3://edi-files/x.pdf")
    def test_allow_retry_after_failed_submission(self, _mock_s3):
        self._complete_documents()
        failed = AttachmentSubmission.objects.create(
            claim=self.claim,
            channel="HCPF_PORTAL",
            status=AttachmentSubmissionStatus.FAILED,
            payload_hash=compute_claim_document_payload_hash(self.claim.id),
            is_active=True,
        )
        response = self.client.post(
            reverse("attachment-submission-submit"),
            {
                "claim_id": self.claim.id,
                "channel": "HCPF_PORTAL",
                "submission_reference": "RETRY-1",
                "allow_retry": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        failed.refresh_from_db()
        self.assertFalse(failed.is_active)
