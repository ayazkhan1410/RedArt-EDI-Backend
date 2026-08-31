from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from apps.claim.models import Claim, SubmissionBatch
from apps.claim_service_line.models import ClaimServiceLine
from apps.core.management.commands.seed_demo_data import (
    SAMPLE_BATCH_NUMBER,
    SAMPLE_CLAIM_NUMBER,
    SAMPLE_MEMBER_ID,
    SAMPLE_NPI,
    SAMPLE_SENDER,
)
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response
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
    def test_seed_creates_approved_sample_rows(self):
        out = StringIO()
        call_command("seed_demo_data", "--flush-all", stdout=out)

        self.assertEqual(
            TradingPartner.objects.filter(sender_id=SAMPLE_SENDER).count(), 1
        )
        self.assertEqual(
            ProviderBillingProfile.objects.filter(npi=SAMPLE_NPI).count(), 1
        )
        self.assertEqual(
            Patient.objects.filter(medicaid_member_id=SAMPLE_MEMBER_ID).count(), 1
        )
        self.assertGreaterEqual(NemtTrip.objects.count(), 1)
        self.assertEqual(
            Claim.objects.filter(claim_number=SAMPLE_CLAIM_NUMBER).count(), 1
        )
        self.assertEqual(ClaimServiceLine.objects.count(), 2)
        self.assertEqual(
            SubmissionBatch.objects.filter(batch_number=SAMPLE_BATCH_NUMBER).count(),
            1,
        )
        self.assertEqual(LongDistanceRule.objects.filter(is_active=True).count(), 2)
        self.assertIn("Approved-sample seed complete", out.getvalue())

        # Idempotent re-run
        call_command("seed_demo_data", stdout=StringIO())
        self.assertEqual(
            Claim.objects.filter(claim_number=SAMPLE_CLAIM_NUMBER).count(), 1
        )
