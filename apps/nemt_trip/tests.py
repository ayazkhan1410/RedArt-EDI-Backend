from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.long_distance_rule.models import LongDistanceRule
from apps.long_distance_rule.utils.counties import resolve_county_type
from apps.long_distance_rule.utils.service import evaluate_trip_mileage
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile


class NemtTripAPITests(APITestCase):
    def setUp(self):
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
            medicaid_member_id="MTRIP001",
            county="Denver",
        )
        self.provider = ProviderBillingProfile.objects.create(
            legal_name="Al Shifa",
            npi="1234567890",
        )

    def test_create_list_and_long_distance_check(self):
        list_url = reverse("nemt-trip-list-create")
        create = self.client.post(
            list_url,
            {
                "patient": self.patient.id,
                "provider": self.provider.id,
                "service_date": "2026-08-30",
                "pickup": "Ali Home",
                "dropoff": "Rural Clinic",
                "one_way_miles": "78.00",
                "mileage_units": 78,
                "charge": "150.00",
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        trip_id = create.data["data"]["id"]

        listed = self.client.get(list_url, {"patient_id": self.patient.id})
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["data"][0]["patient_name"], "Ali Khan")

        check_url = reverse(
            "nemt-trip-long-distance-check", kwargs={"pk": trip_id}
        )
        check = self.client.get(check_url)
        self.assertEqual(check.status_code, status.HTTP_200_OK)
        data = check.data["data"]
        self.assertTrue(data["verification_25_required"])
        self.assertTrue(data["long_distance_review"])
        self.assertTrue(data["attachment_required"])
        self.assertEqual(data["review_threshold"], 52)

    def test_same_pickup_dropoff_rejected(self):
        url = reverse("nemt-trip-list-create")
        response = self.client.post(
            url,
            {
                "patient": self.patient.id,
                "provider": self.provider.id,
                "pickup": "Same Place",
                "dropoff": "same place",
                "one_way_miles": "10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_patient_rejected(self):
        self.patient.is_active = False
        self.patient.save(update_fields=["is_active", "updated_at"])
        url = reverse("nemt-trip-list-create")
        response = self.client.post(
            url,
            {
                "patient": self.patient.id,
                "provider": self.provider.id,
                "pickup": "A",
                "dropoff": "B",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_miles_rejected(self):
        url = reverse("nemt-trip-list-create")
        response = self.client.post(
            url,
            {
                "patient": self.patient.id,
                "provider": self.provider.id,
                "one_way_miles": "-1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LongDistanceRuleAPITests(APITestCase):
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

    def test_list_seeded_rules(self):
        url = reverse("long-distance-rule-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 2)

    def test_duplicate_county_type_rejected(self):
        url = reverse("long-distance-rule-list-create")
        response = self.client.post(
            url,
            {
                "county_type": "STANDARD",
                "review_threshold": 60,
                "verification_threshold": 25,
            },
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
        )

    def test_evaluate_uses_db_thresholds(self):
        result = evaluate_trip_mileage(
            one_way_miles=Decimal("78"),
            mileage_units=78,
            county="Denver",
        )
        self.assertEqual(result["county_type"], "STANDARD")
        self.assertEqual(result["review_threshold"], 52)
        self.assertTrue(result["attachment_required"])

    def test_rural_override_via_county_list(self):
        self.assertEqual(
            resolve_county_type("RuralX", rural_counties={"RuralX"}),
            "DESIGNATED_RURAL",
        )
        result = evaluate_trip_mileage(
            one_way_miles=Decimal("78"),
            mileage_units=78,
            county="RuralX",
            rural_counties={"RuralX"},
        )
        self.assertEqual(result["review_threshold"], 125)
        self.assertFalse(result["long_distance_review"])
        self.assertTrue(result["verification_25_required"])
