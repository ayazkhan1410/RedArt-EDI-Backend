"""Tests for 835 remittance import → Claim PAID / DENIED."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from apps.core.testing import AuthAPITestCase

from apps.claim.choices import ClaimStatus
from apps.claim.models import Claim
from apps.edi.choices import RemittanceClaimOutcome
from apps.edi.models import EDI835Remittance
from apps.edi.tests import EDIFixturesMixin
from apps.edi.utils.import_835 import import_835_remittance
from apps.edi.utils.x12 import map_835_clp_outcome, parse_835
from apps.nemt_trip.models import NemtTrip


SAMPLE_835 = """
ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000905*0*P*:~
GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~
ST*835*0001~
BPR*I*14.90*C*CHK************20260115~
TRN*1*TRACE123456*1234567890~
DTM*405*20260115~
CLP*{claim_paid}*1*14.90*14.90*0*MC*PAYERCTRL1*11~
CAS*CO*45*0~
CLP*{claim_denied}*4*20.00*0*0*MC*PAYERCTRL2*11~
CAS*CO*50*20.00~
CLP*UNKNOWNCLAIM*1*10.00*10.00*0*MC*X*11~
SE*12*0001~
GE*1*1~
IEA*1*000000905~
""".strip()


class Parse835Tests(TestCase):
    def test_map_clp_outcomes(self):
        self.assertEqual(
            map_835_clp_outcome("1", Decimal("14.90")), RemittanceClaimOutcome.PAID
        )
        self.assertEqual(
            map_835_clp_outcome("4", Decimal("0")), RemittanceClaimOutcome.DENIED
        )
        self.assertEqual(
            map_835_clp_outcome("1", Decimal("0")), RemittanceClaimOutcome.DENIED
        )
        self.assertEqual(
            map_835_clp_outcome("22", Decimal("5")), RemittanceClaimOutcome.UNDER_REVIEW
        )

    def test_parse_rejects_non_835(self):
        with self.assertRaises(ValueError):
            parse_835("ST*999*0001~AK9*A*1*1*1~")

    def test_parse_extracts_clp(self):
        parsed = parse_835(
            SAMPLE_835.format(claim_paid="TESTCLAIM0001", claim_denied="TESTCLAIM0002")
        )
        self.assertEqual(parsed["trace_number"], "TRACE123456")
        self.assertEqual(parsed["total_payment"], Decimal("14.90"))
        self.assertEqual(len(parsed["claims"]), 3)
        self.assertEqual(parsed["claims"][0]["outcome"], RemittanceClaimOutcome.PAID)
        self.assertEqual(parsed["claims"][1]["outcome"], RemittanceClaimOutcome.DENIED)


class Import835ServiceTests(EDIFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.claim.status = ClaimStatus.EDI_ACCEPTED
        self.claim.save(update_fields=["status"])
        self.denied_trip = NemtTrip.objects.create(
            patient=self.patient,
            provider=self.provider,
            service_date=date(2026, 8, 31),
            pickup="Home",
            dropoff="Hospital",
            one_way_miles=Decimal("12.00"),
            mileage_units=12,
            charge=Decimal("20.00"),
        )
        self.denied_claim = Claim.objects.create(
            claim_number="TESTCLAIM0002",
            trip=self.denied_trip,
            diagnosis_code="R69",
            place_of_service="03",
            total_charge=Decimal("20.00"),
            status=ClaimStatus.EDI_ACCEPTED,
            is_active=True,
        )

    def test_import_sets_paid_and_denied(self):
        content = SAMPLE_835.format(
            claim_paid=self.claim.claim_number,
            claim_denied=self.denied_claim.claim_number,
        )
        remittance, updated_ids, meta = import_835_remittance(content=content)
        self.assertFalse(meta["idempotent"])
        self.claim.refresh_from_db()
        self.denied_claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.PAID)
        self.assertEqual(self.denied_claim.status, ClaimStatus.DENIED)
        self.assertEqual(remittance.claim_line_count, 3)
        self.assertEqual(remittance.applied_claim_count, 2)
        self.assertIn(self.claim.id, updated_ids)
        self.assertIn(self.denied_claim.id, updated_ids)

    def test_idempotent_reimport(self):
        content = SAMPLE_835.format(
            claim_paid=self.claim.claim_number,
            claim_denied=self.denied_claim.claim_number,
        )
        first, _, _ = import_835_remittance(content=content)
        second, _, meta = import_835_remittance(content=content)
        self.assertTrue(meta["idempotent"])
        self.assertEqual(first.id, second.id)
        self.assertEqual(EDI835Remittance.objects.filter(is_active=True).count(), 1)

    def test_does_not_overwrite_paid_with_under_review(self):
        self.claim.status = ClaimStatus.PAID
        self.claim.save(update_fields=["status"])
        # CLP02=22 → UNDER_REVIEW; must not clobber PAID
        content = (
            "ST*835*0001~\n"
            f"CLP*{self.claim.claim_number}*22*14.90*1.00*0*MC*X*11~\n"
        )
        import_835_remittance(content=content)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.PAID)


class Import835APITests(EDIFixturesMixin, AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.claim.status = ClaimStatus.EDI_ACCEPTED
        self.claim.save(update_fields=["status"])

    def test_import_endpoint(self):
        content = SAMPLE_835.format(
            claim_paid=self.claim.claim_number,
            claim_denied="NOPE_DENIED",
        )
        response = self.client.post(
            reverse("edi-835-remittance-import"),
            {"content": content, "apply_claim_status": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.PAID)
        remittance_id = response.data["data"]["id"]
        detail = self.client.get(
            reverse("edi-835-remittance-detail", kwargs={"pk": remittance_id})
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(detail.data["data"]["claim_payments"]), 2)
