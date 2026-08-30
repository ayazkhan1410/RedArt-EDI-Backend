from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.claim.choices import BatchStatus, ClaimStatus, DocumentStatus, DocumentType
from apps.claim.models import BatchClaim, Claim, ClaimDocument, SubmissionBatch
from apps.claim.utils.service import create_claim_from_trip, sync_claim_document_status
from apps.edi.choices import EDIFileStatus
from apps.edi.models import EDIControlNumber, EDIFile
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
            medicaid_member_id="MEDI001",
            county="Denver",
        )
        self.provider = ProviderBillingProfile.objects.create(
            legal_name="Al Shifa",
            npi="1234567890",
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
            create_service_line=False,
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

    def test_create_edi_file_and_mark_uploaded(self):
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
