from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from apps.claim.models import BatchClaim, Claim, ClaimDocument, SubmissionBatch
from apps.claim_service_line.models import ClaimServiceLine
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response
from apps.edi.models import EDIControlNumber, EDIFile
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile
from apps.trading_partner.models import TradingPartner


class StandardPaginationTests(SimpleTestCase):
    def test_invalid_page_size_raises(self):
        pagination = StandardPagination()

        class FakeRequest:
            query_params = {"page_size": "abc"}

        with self.assertRaises(ValidationError):
            pagination.get_page_size(FakeRequest())

    def test_valid_page_size_capped(self):
        pagination = StandardPagination()

        class FakeRequest:
            query_params = {"page_size": "999"}

        self.assertEqual(pagination.get_page_size(FakeRequest()), 200)


class ResponseHelperTests(SimpleTestCase):
    def test_success_and_error_shape(self):
        ok = success_response("done", data={"id": 1})
        self.assertTrue(ok.data["success"])
        self.assertEqual(ok.data["data"]["id"], 1)

        err = error_response("bad", errors={"field": ["x"]})
        self.assertFalse(err.data["success"])
        self.assertIn("errors", err.data)


class SeedDemoDataTests(TestCase):
    def test_seed_creates_at_least_five_per_model(self):
        call_command("seed_demo_data")

        self.assertGreaterEqual(TradingPartner.objects.count(), 5)
        self.assertGreaterEqual(ProviderBillingProfile.objects.count(), 5)
        self.assertGreaterEqual(Patient.objects.count(), 5)
        self.assertGreaterEqual(NemtTrip.objects.count(), 5)
        self.assertEqual(
            LongDistanceRule.objects.filter(is_active=True).count(),
            2,
        )
        self.assertGreaterEqual(Claim.objects.count(), 5)
        self.assertGreaterEqual(ClaimServiceLine.objects.count(), 5)
        self.assertGreaterEqual(ClaimDocument.objects.count(), 5)
        self.assertGreaterEqual(SubmissionBatch.objects.count(), 5)
        self.assertGreaterEqual(BatchClaim.objects.count(), 1)
        self.assertGreaterEqual(EDIControlNumber.objects.count(), 1)
        self.assertGreaterEqual(EDIFile.objects.count(), 1)

        # Idempotent re-run should not explode / duplicate claim numbers
        call_command("seed_demo_data")
        self.assertEqual(
            Claim.objects.filter(claim_number__startswith="DEMO-").count(),
            5,
        )
        self.assertEqual(
            SubmissionBatch.objects.filter(
                batch_number__startswith="DEMO-"
            ).count(),
            5,
        )
