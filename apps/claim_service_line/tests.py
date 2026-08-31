from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from apps.core.testing import AuthAPITestCase

from apps.claim.models import Claim
from apps.claim_service_line.models import ClaimServiceLine
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile


class ClaimServiceLineAPITests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.patient = Patient.objects.create(
            first_name="Ali",
            last_name="Khan",
            date_of_birth=date(1995, 5, 12),
            medicaid_member_id="M999888777",
            county="Denver",
        )
        self.provider = ProviderBillingProfile.objects.create(
            legal_name="Provider LLC",
            npi="1098765432",
        )
        self.trip = NemtTrip.objects.create(
            patient=self.patient,
            provider=self.provider,
            service_date=date(2026, 8, 30),
            one_way_miles=Decimal("10.00"),
            mileage_units=10,
            charge=Decimal("50.00"),
        )
        self.claim = Claim.objects.create(
            claim_number="C-SL-1",
            trip=self.trip,
            total_charge=Decimal("50.00"),
        )

    def test_create_and_list_by_claim(self):
        create_url = reverse("claim-service-line-list-create")
        response = self.client.post(
            create_url,
            {
                "claim": self.claim.id,
                "procedure_code": "A0100",
                "from_date": "2026-08-30",
                "to_date": "2026-08-30",
                "units": 10,
                "mileage": "10.00",
                "charge": "50.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        line_id = response.data["data"]["id"]

        list_response = self.client.get(create_url, {"claim_id": self.claim.id})
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["data"][0]["id"], line_id)
        self.assertEqual(ClaimServiceLine.objects.count(), 1)

    def test_negative_charge_rejected(self):
        url = reverse("claim-service-line-list-create")
        response = self.client.post(
            url,
            {
                "claim": self.claim.id,
                "procedure_code": "A0100",
                "charge": "-1.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete(self):
        line = ClaimServiceLine.objects.create(
            claim=self.claim,
            procedure_code="A0100",
            units=5,
            charge=Decimal("25.00"),
        )
        url = reverse("claim-service-line-detail", kwargs={"pk": line.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        line.refresh_from_db()
        self.assertFalse(line.is_active)
