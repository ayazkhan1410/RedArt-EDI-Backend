from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.claim.choices import AttachmentStatus, ClaimStatus
from apps.claim.models import BatchClaim, Claim
from apps.claim.utils.service import create_claim_from_trip
from apps.claim_service_line.models import ClaimServiceLine
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile
from apps.trading_partner.models import TradingPartner


class ClaimFixturesMixin:
    def setUp(self):
        LongDistanceRule.objects.update_or_create(
            county_type="STANDARD",
            defaults={
                "review_threshold": 52,
                "verification_threshold": 25,
                "is_active": True,
            },
        )
        LongDistanceRule.objects.update_or_create(
            county_type="DESIGNATED_RURAL",
            defaults={
                "review_threshold": 125,
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


class ClaimServiceTests(ClaimFixturesMixin, TestCase):
    def test_create_from_trip_sets_long_distance_flags(self):
        claim, line = create_claim_from_trip(
            trip_id=self.trip.id,
            claim_number="C001",
            external_id="TRIP-1001",
            diagnosis_code="R68.89",
            place_of_service="41",
        )
        self.assertEqual(claim.status, ClaimStatus.DOCUMENTS_REQUIRED)
        self.assertTrue(claim.attachment_required)
        self.assertEqual(claim.attachment_status, AttachmentStatus.PENDING)
        self.assertIsNotNone(line)
        self.assertEqual(line.procedure_code, "A0100")
        self.assertEqual(line.units, 78)

    def test_one_claim_per_trip(self):
        create_claim_from_trip(trip_id=self.trip.id, claim_number="C001")
        with self.assertRaises(ValueError):
            create_claim_from_trip(trip_id=self.trip.id, claim_number="C002")


class ClaimAPITests(ClaimFixturesMixin, APITestCase):
    def test_create_from_trip_api(self):
        url = reverse("claim-from-trip")
        response = self.client.post(
            url,
            {
                "trip_id": self.trip.id,
                "claim_number": "C001",
                "external_id": "TRIP-1001",
                "diagnosis_code": "R68.89",
                "place_of_service": "41",
                "procedure_code": "A0100",
                "create_service_line": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("id", response.data["data"])
        self.assertIn("service_line_id", response.data["data"])

        claim = Claim.objects.get(pk=response.data["data"]["id"])
        self.assertTrue(claim.attachment_required)
        self.assertEqual(
            ClaimServiceLine.objects.filter(claim=claim).count(), 1
        )

    def test_duplicate_trip_returns_409_or_400(self):
        create_claim_from_trip(trip_id=self.trip.id, claim_number="C001")
        url = reverse("claim-from-trip")
        response = self.client.post(
            url,
            {"trip_id": self.trip.id, "claim_number": "C002"},
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
        )

    def test_list_claims_no_n_plus_one_shape(self):
        create_claim_from_trip(trip_id=self.trip.id, claim_number="C001")
        url = reverse("claim-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["data"][0]
        self.assertEqual(row["patient_id"], self.patient.id)
        self.assertEqual(row["provider_id"], self.provider.id)

    def test_service_line_date_validation(self):
        claim, _ = create_claim_from_trip(
            trip_id=self.trip.id,
            claim_number="C001",
            create_service_line=False,
        )
        url = reverse("claim-service-line-list-create")
        response = self.client.post(
            url,
            {
                "claim": claim.id,
                "procedure_code": "A0100",
                "from_date": "2026-08-31",
                "to_date": "2026-08-30",
                "units": 10,
                "charge": "50.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_soft_delete_claim(self):
        claim, _ = create_claim_from_trip(
            trip_id=self.trip.id,
            claim_number="C001",
            create_service_line=False,
        )
        url = reverse("claim-detail", kwargs={"pk": claim.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        claim.refresh_from_db()
        self.assertFalse(claim.is_active)


class ClaimDocumentAndBatchTests(ClaimFixturesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.claim, _ = create_claim_from_trip(
            trip_id=self.trip.id,
            claim_number="C001",
            external_id="TRIP-1001",
            create_service_line=False,
        )
        self.partner = TradingPartner.objects.create(
            name="Colorado Medicaid",
            sender_id="TP123456",
            receiver_id="COMEDASSISTPROG",
            environment="TEST",
        )

    def _create_doc(self, document_type, file_name, document_hash):
        url = reverse("claim-document-list-create")
        return self.client.post(
            url,
            {
                "claim": self.claim.id,
                "document_type": document_type,
                "file_name": file_name,
                "document_hash": document_hash,
                "is_signed": True,
                "status": "COMPLETE",
            },
            format="json",
        )

    def test_missing_docs_block_batch_and_keep_documents_required(self):
        self.assertEqual(self.claim.status, ClaimStatus.DOCUMENTS_REQUIRED)

        batch_url = reverse("submission-batch-list-create")
        batch = self.client.post(
            batch_url,
            {
                "batch_number": "RB-2026-10048",
                "trading_partner": self.partner.id,
                "environment": "TEST",
                "status": "READY",
            },
            format="json",
        )
        self.assertEqual(batch.status_code, status.HTTP_201_CREATED)
        batch_id = batch.data["data"]["id"]

        add_url = reverse(
            "submission-batch-add-claim", kwargs={"pk": batch_id}
        )
        blocked = self.client.post(
            add_url, {"claim_id": self.claim.id, "st02": "0001"}, format="json"
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("blocked", blocked.data["message"].lower())

    def test_complete_docs_ready_for_837p_and_batch(self):
        trip_log = self._create_doc(
            "STANDARD_TRIP_LOG", "trip_log_C001.pdf", "HASH111"
        )
        self.assertEqual(trip_log.status_code, status.HTTP_201_CREATED)

        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.DOCUMENTS_REQUIRED)

        verification = self._create_doc(
            "MILE_25_VERIFICATION", "verification_C001.pdf", "HASH222"
        )
        self.assertEqual(verification.status_code, status.HTTP_201_CREATED)

        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.READY_FOR_837P)

        status_url = reverse(
            "claim-document-status", kwargs={"pk": self.claim.id}
        )
        status_resp = self.client.get(status_url)
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(status_resp.data["data"]["can_submit"])

        batch = self.client.post(
            reverse("submission-batch-list-create"),
            {
                "batch_number": "RB-2026-10048",
                "trading_partner": self.partner.id,
                "environment": "TEST",
                "status": "READY",
            },
            format="json",
        )
        batch_id = batch.data["data"]["id"]
        added = self.client.post(
            reverse("submission-batch-add-claim", kwargs={"pk": batch_id}),
            {"claim_id": self.claim.id, "st02": "0001"},
            format="json",
        )
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)
        self.assertEqual(added.data["data"]["st02"], "0001")

        batch_detail = self.client.get(
            reverse("submission-batch-detail", kwargs={"pk": batch_id})
        )
        self.assertEqual(batch_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(batch_detail.data["data"]["claim_count"], 1)
        self.assertEqual(
            str(batch_detail.data["data"]["total_amount"]),
            "150.00",
        )
        self.assertEqual(BatchClaim.objects.filter(batch_id=batch_id).count(), 1)

    def test_attachment_submission_confirms_claim_attachment_status(self):
        self._create_doc("STANDARD_TRIP_LOG", "trip_log_C001.pdf", "HASH111")
        self._create_doc("MILE_25_VERIFICATION", "verification_C001.pdf", "HASH222")
        self.claim.refresh_from_db()
        self.assertTrue(self.claim.attachment_required)

        response = self.client.post(
            reverse("attachment-submission-list-create"),
            {
                "claim": self.claim.id,
                "channel": "HCPF_PORTAL",
                "submission_reference": "HCPF-ATT-789",
                "status": "CONFIRMED",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.attachment_status, AttachmentStatus.CONFIRMED)

        listed = self.client.get(
            reverse("attachment-submission-list-create"),
            {"claim_id": self.claim.id},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(listed.data["count"], 1)
