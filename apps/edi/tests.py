from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.claim.choices import BatchStatus, ClaimStatus, DocumentStatus, DocumentType
from apps.claim.models import BatchClaim, Claim, ClaimDocument, SubmissionBatch
from apps.claim.utils.service import create_claim_from_trip, sync_claim_document_status
from apps.edi.choices import EDIFileStatus, TransferLogStatus
from apps.edi.models import EDIControlNumber, EDIFile, EDIFileTransferLog
from apps.edi.utils.envelope import get_edi_envelope_config
from apps.edi.utils.readiness import assert_batch_ready_for_837p_generation
from apps.edi.utils.service import (
    allocate_control_numbers,
    build_colorado_837p_filename,
    create_edi_file_for_batch,
    mark_edi_file_uploaded,
)
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile
from apps.trading_partner.models import TradingPartner


class EDIFixturesMixin:
    def setUp(self):
        LongDistanceRule.objects.update_or_create(
            county_type="STANDARD",
            defaults={
                "review_threshold": 52,
                "verification_threshold": 25,
                "is_active": True,
            },
        )
        self.partner = TradingPartner.objects.create(
            name="Colorado Medicaid",
            sender_id="TP123456",
            receiver_id="COMEDASSISTPROG",
            environment="TEST",
        )
        self.patient = Patient.objects.create(
            first_name="Ali",
            last_name="Khan",
            date_of_birth=date(1995, 5, 12),
            gender="M",
            medicaid_member_id="MEDI001",
            county="Denver",
            address_line_1="100 Main St",
            city="Denver",
            state="CO",
            zip="80202",
            phone="3035550100",
        )
        self.provider = ProviderBillingProfile.objects.create(
            legal_name="Al Shifa",
            billing_name="Al Shifa Transportation",
            npi="1234567890",
            taxonomy_code="343900000X",
            address_line_1="100 Main St",
            city="Denver",
            state="CO",
            zip="80202",
            phone="3035550199",
        )
        self.trip = NemtTrip.objects.create(
            patient=self.patient,
            provider=self.provider,
            service_date=date(2026, 8, 30),
            pickup="Home",
            dropoff="Clinic",
            one_way_miles=Decimal("78.00"),
            mileage_units=78,
            charge=Decimal("150.00"),
        )
        self.claim, _ = create_claim_from_trip(
            trip_id=self.trip.id,
            claim_number="C-EDI-1",
            diagnosis_code="R68.89",
            place_of_service="41",
            create_service_line=True,
        )
        for doc_type, name, digest in (
            (DocumentType.STANDARD_TRIP_LOG, "trip.pdf", "H1"),
            (DocumentType.MILE_25_VERIFICATION, "v25.pdf", "H2"),
        ):
            ClaimDocument.objects.create(
                claim=self.claim,
                document_type=doc_type,
                file_name=name,
                document_hash=digest,
                is_signed=True,
                status=DocumentStatus.COMPLETE,
            )
        sync_claim_document_status(self.claim)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.READY_FOR_837P)

        self.batch = SubmissionBatch.objects.create(
            batch_number="RB-EDI-10048",
            trading_partner=self.partner,
            environment="TEST",
            status=BatchStatus.READY,
        )
        BatchClaim.objects.create(
            batch=self.batch,
            claim=self.claim,
            st02="0001",
        )
        self.batch.claim_count = 1
        self.batch.total_amount = Decimal("150.00")
        self.batch.save(update_fields=["claim_count", "total_amount", "updated_at"])


class EDIServiceTests(EDIFixturesMixin, TestCase):
    def test_allocate_control_numbers_and_filename(self):
        row, created = allocate_control_numbers(batch_id=self.batch.id)
        self.assertTrue(created)
        self.assertEqual(row.isa13, "000000001")
        self.assertEqual(row.gs06, "1")
        self.assertEqual(row.environment, "TEST")

        again, created_again = allocate_control_numbers(batch_id=self.batch.id)
        self.assertFalse(created_again)
        self.assertEqual(again.id, row.id)

        name = build_colorado_837p_filename(sender_id="TP123456")
        self.assertTrue(name.startswith("TP123456-837P-"))
        self.assertTrue(name.endswith("-1of1.txt"))

        envelope = get_edi_envelope_config("TEST")
        self.assertEqual(envelope["isa15"], "T")
        self.assertEqual(envelope["gs08"], "005010X222A1")
        self.assertEqual(get_edi_envelope_config("PRODUCTION")["isa15"], "P")

    def test_create_edi_file_and_mark_uploaded(self):
        assert_batch_ready_for_837p_generation(self.batch)
        edi_file = create_edi_file_for_batch(
            batch_id=self.batch.id,
            file_hash="FILEHASH123",
            path_or_blob_ref="s3://edi/001.txt",
        )
        self.assertEqual(edi_file.transaction_type, "837P")
        self.assertEqual(edi_file.status, EDIFileStatus.GENERATED)
        self.assertIsNotNone(edi_file.control_number_id)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.GENERATED)

        uploaded = mark_edi_file_uploaded(
            edi_file.id,
            path_or_blob_ref="s3://edi/001.txt",
            file_hash="FILEHASH123",
        )
        self.assertEqual(uploaded.status, EDIFileStatus.UPLOADED)
        self.assertIsNotNone(uploaded.uploaded_at)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.SUBMITTED)

    def test_missing_patient_demographics_blocks_edi_file(self):
        self.patient.address_line_1 = None
        self.patient.save(update_fields=["address_line_1", "updated_at"])
        with self.assertRaises(ValueError):
            create_edi_file_for_batch(batch_id=self.batch.id)


class EDIAPITests(EDIFixturesMixin, APITestCase):
    def test_allocate_and_from_batch_apis(self):
        alloc = self.client.post(
            reverse("edi-control-number-allocate"),
            {"batch_id": self.batch.id, "environment": "TEST"},
            format="json",
        )
        self.assertEqual(alloc.status_code, status.HTTP_201_CREATED)
        self.assertEqual(alloc.data["data"]["isa13"], "000000001")

        created = self.client.post(
            reverse("edi-file-from-batch"),
            {
                "batch_id": self.batch.id,
                "transaction_type": "837P",
                "file_hash": "FILEHASH123",
                "path_or_blob_ref": "s3://edi/001.txt",
                "status": "GENERATED",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        file_id = created.data["data"]["id"]
        self.assertTrue(
            created.data["data"]["filename"].startswith("TP123456-837P-")
        )

        marked = self.client.post(
            reverse("edi-file-mark-uploaded", kwargs={"pk": file_id}),
            {"path_or_blob_ref": "s3://edi/001.txt", "file_hash": "FILEHASH123"},
            format="json",
        )
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertEqual(marked.data["data"]["status"], "UPLOADED")

        listed = self.client.get(
            reverse("edi-file-list-create"), {"batch_id": self.batch.id}
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)

        controls = self.client.get(
            reverse("edi-control-number-list-create"),
            {"batch_id": self.batch.id},
        )
        self.assertEqual(controls.status_code, status.HTTP_200_OK)
        self.assertEqual(controls.data["count"], 1)
        self.assertEqual(EDIControlNumber.objects.count(), 1)
        self.assertEqual(EDIFile.objects.count(), 1)

    def test_empty_batch_cannot_create_file(self):
        empty = SubmissionBatch.objects.create(
            batch_number="RB-EMPTY",
            trading_partner=self.partner,
            environment="TEST",
            status=BatchStatus.READY,
            claim_count=0,
        )
        response = self.client.post(
            reverse("edi-file-from-batch"),
            {"batch_id": empty.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class Generate837PTests(EDIFixturesMixin, APITestCase):
    def test_handler_and_generate_api(self):
        from apps.edi.utils.handler import Generate837PHandler
        from apps.edi.utils.schema import build_edi_content, render_edi_file

        handler = Generate837PHandler(self.batch.id)
        payload = handler.build_payload_dict()
        self.assertEqual(payload["trading_partner"]["sender_id"], "TP123456")
        self.assertEqual(len(payload["claims"]), 1)
        segments = build_edi_content(payload)
        body = render_edi_file(segments)
        self.assertIn("ISA*", body)
        self.assertIn("COMEDASSISTPROG", body)
        self.assertIn("CO_TXIX", body)
        self.assertIn("ST*837*", body)
        # 2000A: PRV before 2010AA NM1; 2010AA: REF*EI after N4
        hl_i = body.index("HL*1**20*1~")
        prv_i = body.index("PRV*BI*PXC*")
        nm1_i = body.index("NM1*85*")
        ref_i = body.index("REF*EI*")
        self.assertLess(hl_i, prv_i)
        self.assertLess(prv_i, nm1_i)
        self.assertLess(nm1_i, ref_i)
        self.assertTrue(body.strip().endswith("IEA*1*000000001~") or "IEA*1*" in body)

        edi_file, _, _ = handler.generate()
        self.assertEqual(edi_file.status, EDIFileStatus.GENERATED)
        self.assertTrue(edi_file.filename.startswith("TP123456-837P-"))
        self.assertTrue(edi_file.file_hash)

        # Second generate via API on same batch still allowed (new file)
        response = self.client.post(
            reverse("edi-file-generate-837p"),
            {"batch_id": self.batch.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["status"], "GENERATED")

    def test_queue_upload_writes_transfer_logs(self):
        from unittest.mock import patch

        from apps.edi.choices import TransferLogStatus
        from apps.edi.models import EDIFileTransferLog, SFTPCredentials, SFTPDirectory
        from apps.edi.utils.handler import Generate837PHandler

        edi_file, _, _ = Generate837PHandler(self.batch.id).generate()
        cred = SFTPCredentials.objects.create(
            name="TEST-SFTP",
            trading_partner=self.partner,
            environment="TEST",
            host="127.0.0.1",
            port=22,
            username="user",
            auth_type="PASSWORD",
            password="secret",
            is_active=True,
        )
        SFTPDirectory.objects.create(
            credentials=cred,
            name="outbound",
            purpose="OUTBOUND_837P",
            sending_path="/send",
            receiving_path="/recv",
            is_active=True,
        )

        with self.settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_STORE_EAGER_RESULT=True):
            with patch(
                "apps.edi.utils.upload.upload_bytes_via_sftp",
                return_value="/send/" + edi_file.filename,
            ), patch(
                "apps.edi.utils.upload.upload_bytes_to_s3",
                return_value="s3://edi-files/edi/837p/1/" + edi_file.filename,
            ):
                response = self.client.post(
                    reverse("edi-file-queue-upload", kwargs={"pk": edi_file.id}),
                    {},
                    format="json",
                )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        edi_file.refresh_from_db()
        self.assertEqual(edi_file.status, EDIFileStatus.UPLOADED)
        logs = EDIFileTransferLog.objects.filter(edi_file=edi_file)
        self.assertEqual(logs.count(), 2)
        self.assertTrue(
            logs.filter(channel="SFTP", status=TransferLogStatus.SUCCESS).exists()
        )
        self.assertTrue(
            logs.filter(channel="S3", status=TransferLogStatus.SUCCESS).exists()
        )

        listed = self.client.get(
            reverse("edi-file-transfer-log-list"),
            {"edi_file_id": edi_file.id},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 2)

        # Resend allowed after UPLOADED
        with self.settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_STORE_EAGER_RESULT=True):
            with patch(
                "apps.edi.utils.upload.upload_bytes_via_sftp",
                return_value="/send/" + edi_file.filename,
            ), patch(
                "apps.edi.utils.upload.upload_bytes_to_s3",
                return_value="s3://edi-files/edi/837p/1/" + edi_file.filename,
            ):
                again = self.client.post(
                    reverse("edi-file-queue-upload", kwargs={"pk": edi_file.id}),
                    {"credentials_id": cred.id},
                    format="json",
                )
        self.assertEqual(again.status_code, status.HTTP_202_ACCEPTED)
        edi_file.refresh_from_db()
        self.assertEqual(edi_file.status, EDIFileStatus.UPLOADED)
        self.assertEqual(
            EDIFileTransferLog.objects.filter(edi_file=edi_file).count(),
            4,
        )


class EDIAcknowledgementAPITests(EDIFixturesMixin, APITestCase):
    def test_apply_999_sets_edi_accepted_not_paid(self):
        edi = create_edi_file_for_batch(
            batch_id=self.batch.id,
            file_hash="ACKHASH1",
            path_or_blob_ref="media/edi/demo.txt",
        )
        mark_edi_file_uploaded(edi.id)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.EDI_SENT)

        response = self.client.post(
            reverse("edi-acknowledgement-apply"),
            {
                "batch_id": self.batch.id,
                "ack_type": "999",
                "status": "ACCEPTED",
                "affected_st02": "0001",
                "raw_file_ref": "s3://edi/999_001.edi",
                "apply_claim_status": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["status"], "ACCEPTED")
        self.assertIn(self.claim.id, response.data["data"]["updated_claim_ids"])

        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.EDI_ACCEPTED)
        self.assertNotEqual(self.claim.status, ClaimStatus.PAID)

        edi.refresh_from_db()
        self.assertEqual(edi.status, EDIFileStatus.ACKNOWLEDGED)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACKNOWLEDGED)

        listed = self.client.get(
            reverse("edi-acknowledgement-list-create"),
            {"batch_id": self.batch.id},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(listed.data["count"], 1)
