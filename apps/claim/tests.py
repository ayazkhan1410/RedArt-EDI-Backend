from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.claim.choices import AttachmentStatus, ClaimStatus
from apps.claim.models import Claim
from apps.claim.utils.service import create_claim_from_trip
from apps.claim_service_line.models import ClaimServiceLine
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile


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
