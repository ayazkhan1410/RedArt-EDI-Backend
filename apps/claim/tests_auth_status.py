"""JWT auth + claim validate/status API tests."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.claim.choices import ClaimStatus, DocumentStatus, DocumentType
from apps.claim.models import ClaimDocument, SubmissionBatch
from apps.claim.utils.service import create_claim_from_trip, validate_claim_for_edi
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile
from apps.trading_partner.models import TradingPartner


User = get_user_model()


class AuthJWTAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="redart_service",
            password="test-password-123",
            email="service@redart.example",
        )

    def test_obtain_refresh_and_verify_token(self):
        obtain = self.client.post(
            reverse("auth-token-obtain"),
            {"username": "redart_service", "password": "test-password-123"},
            format="json",
        )
        self.assertEqual(obtain.status_code, status.HTTP_200_OK)
        self.assertIn("access", obtain.data)
        self.assertIn("refresh", obtain.data)

        refresh = self.client.post(
            reverse("auth-token-refresh"),
            {"refresh": obtain.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh.data)

        verify = self.client.post(
            reverse("auth-token-verify"),
            {"token": obtain.data["access"]},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

    def test_jwt_bearer_authenticates_service_user(self):
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory
        from rest_framework_simplejwt.authentication import JWTAuthentication

        token = str(RefreshToken.for_user(self.user).access_token)
        factory = APIRequestFactory()
        django_request = factory.get("/api/v1/claims/")
        django_request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        auth = JWTAuthentication().authenticate(Request(django_request))
        self.assertIsNotNone(auth)
        self.assertEqual(auth[0].pk, self.user.pk)

    def test_is_authenticated_rejects_anonymous_request(self):
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.response import Response
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView
        from rest_framework_simplejwt.authentication import JWTAuthentication

        class _Protected(APIView):
            authentication_classes = [JWTAuthentication]
            permission_classes = [IsAuthenticated]

            def get(self, request):
                return Response({"ok": True})

        factory = APIRequestFactory()
        view = _Protected.as_view()
        anon = view(factory.get("/"))
        self.assertEqual(anon.status_code, status.HTTP_401_UNAUTHORIZED)

        token = str(RefreshToken.for_user(self.user).access_token)
        authed_req = factory.get("/")
        authed_req.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        ok = view(authed_req)
        self.assertEqual(ok.status_code, status.HTTP_200_OK)


class ClaimValidateStatusAPITests(APITestCase):
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
            name="REDART LLC",
            sender_id="89513013",
            receiver_id="COMEDASSISTPROG",
            environment="TEST",
        )
        self.patient = Patient.objects.create(
            first_name="JANE",
            last_name="TESTPATIENT",
            date_of_birth=date(1950, 1, 1),
            gender="F",
            medicaid_member_id="Y999999",
            county="Pueblo",
            address_line_1="100 TEST STREET",
            city="PUEBLO",
            state="CO",
            zip="81001",
        )
        self.provider = ProviderBillingProfile.objects.create(
            legal_name="REDART LLC",
            billing_name="REDART LLC",
            npi="9000211959",
            address_line_1="1276 SANDALWOOD DR APT B",
            city="COLORADO SPRINGS",
            state="CO",
            zip="80918",
        )
        self.trip = NemtTrip.objects.create(
            patient=self.patient,
            provider=self.provider,
            service_date=date(2026, 8, 5),
            pickup="Home",
            dropoff="Clinic",
            one_way_miles=Decimal("8.00"),
            mileage_units=1,
            charge=Decimal("14.90"),
        )
        self.claim, _ = create_claim_from_trip(
            trip_id=self.trip.id,
            claim_number="TESTCLAIM-VAL-1",
            diagnosis_code="R69",
            place_of_service="03",
        )
        self.batch = SubmissionBatch.objects.create(
            batch_number="BATCH-VAL-1",
            trading_partner=self.partner,
            environment="TEST",
            is_active=True,
        )

    def test_validate_ready_short_trip(self):
        response = self.client.post(
            reverse("claim-validate", kwargs={"pk": self.claim.id}),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertTrue(data["ready"])
        self.assertEqual(data["errors"], [])
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.READY_FOR_837P)

    def test_validate_not_ready_missing_demographics(self):
        self.patient.address_line_1 = None
        self.patient.save(update_fields=["address_line_1", "updated_at"])
        response = self.client.post(
            reverse("claim-validate", kwargs={"pk": self.claim.id}),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertFalse(data["ready"])
        self.assertTrue(any("demographics" in e.lower() for e in data["errors"]))

    def test_validate_long_distance_needs_docs(self):
        self.trip.one_way_miles = Decimal("78.00")
        self.trip.mileage_units = 78
        self.trip.save(update_fields=["one_way_miles", "mileage_units", "updated_at"])
        from apps.claim.utils.service import apply_long_distance_flags

        apply_long_distance_flags(self.claim, self.trip)
        self.claim.save()
        result = validate_claim_for_edi(self.claim, update_status=True)
        self.assertFalse(result["ready"])
        self.assertTrue(any("document" in e.lower() for e in result["errors"]))

        ClaimDocument.objects.create(
            claim=self.claim,
            document_type=DocumentType.STANDARD_TRIP_LOG,
            file_name="trip.pdf",
            document_hash="HASH1",
            status=DocumentStatus.COMPLETE,
            is_signed=True,
            is_active=True,
        )
        ClaimDocument.objects.create(
            claim=self.claim,
            document_type=DocumentType.MILE_25_VERIFICATION,
            file_name="verify.pdf",
            document_hash="HASH2",
            status=DocumentStatus.COMPLETE,
            is_signed=True,
            is_active=True,
        )
        result2 = validate_claim_for_edi(self.claim, update_status=True)
        self.assertTrue(result2["ready"])

    def test_claim_and_batch_status_endpoints(self):
        from apps.claim.utils.service import add_claim_to_batch

        add_claim_to_batch(batch_id=self.batch.id, claim_id=self.claim.id, st02="0001")

        claim_status = self.client.get(
            reverse("claim-status", kwargs={"pk": self.claim.id})
        )
        self.assertEqual(claim_status.status_code, status.HTTP_200_OK)
        cdata = claim_status.data["data"]
        self.assertEqual(cdata["claim_id"], self.claim.id)
        self.assertIn("ready", cdata)
        self.assertEqual(cdata["batch"]["batch_number"], "BATCH-VAL-1")

        batch_status = self.client.get(
            reverse("submission-batch-status", kwargs={"pk": self.batch.id})
        )
        self.assertEqual(batch_status.status_code, status.HTTP_200_OK)
        bdata = batch_status.data["data"]
        self.assertEqual(bdata["batch_id"], self.batch.id)
        self.assertEqual(len(bdata["claims"]), 1)


class ValidateClaimServiceTests(TestCase):
    def test_missing_claim_returns_not_ready(self):
        result = validate_claim_for_edi(None)
        self.assertFalse(result["ready"])
        self.assertTrue(result["errors"])
