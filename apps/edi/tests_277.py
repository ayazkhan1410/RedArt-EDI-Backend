"""277 claim status import tests."""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from apps.claim.choices import ClaimStatus
from apps.core.testing import AuthAPITestCase
from apps.edi.choices import AcknowledgementType
from apps.edi.models import EDIAcknowledgement
from apps.edi.tests import EDIFixturesMixin
from apps.edi.utils.service import create_edi_file_for_batch, mark_edi_file_uploaded
from apps.edi.utils.x12 import parse_277


class Parse277Tests(EDIFixturesMixin, TestCase):
    def _sample_277(self, claim_number="C-EDI-1"):
        return (
            "ISA*00*          *00*          *ZZ*COMEDASSISTPROG*ZZ*89513013       "
            "*260817*1947*^*00501*000000001*0*T*:~"
            "GS*HN*COMEDASSISTPROG*89513013*20260817*1947*1*X*005010X214~"
            "ST*277*0001*005010X214~"
            f"TRN*2*TRACK001~"
            f"REF*D9*{claim_number}~"
            "STC*A2:19:PR~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )

    def test_parse_277_maps_stc_to_under_review(self):
        parsed = parse_277(self._sample_277())
        self.assertEqual(parsed["ack_type"], AcknowledgementType.X277)
        self.assertEqual(parsed["affected_st02"], "0001")
        self.assertEqual(len(parsed["claim_statuses"]), 1)
        line = parsed["claim_statuses"][0]
        self.assertEqual(line["claim_number"], "C-EDI-1")
        self.assertEqual(line["outcome"], ClaimStatus.UNDER_REVIEW)


class Import277APITests(EDIFixturesMixin, AuthAPITestCase):
    def _sample_277(self, claim_number="C-EDI-1"):
        return (
            "ISA*00*          *00*          *ZZ*COMEDASSISTPROG*ZZ*89513013       "
            "*260817*1947*^*00501*000000001*0*T*:~"
            "GS*HN*COMEDASSISTPROG*89513013*20260817*1947*1*X*005010X214~"
            "ST*277*0001*005010X214~"
            f"TRN*2*TRACK001~"
            f"REF*D9*{claim_number}~"
            "STC*A2:19:PR~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )

    def test_import_277_updates_claim_status(self):
        edi = create_edi_file_for_batch(
            batch_id=self.batch.id,
            file_hash="277HASH1",
            path_or_blob_ref="media/edi/277_001.edi",
        )
        mark_edi_file_uploaded(edi.id)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.EDI_SENT)

        response = self.client.post(
            reverse("edi-acknowledgement-import-277"),
            {
                "batch_id": self.batch.id,
                "edi_file_id": edi.id,
                "raw_file_ref": "s3://edi/277_001.edi",
                "content": self._sample_277(),
                "apply_claim_status": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["status"], "ACCEPTED")
        self.assertIn(self.claim.id, response.data["data"]["updated_claim_ids"])
        self.assertEqual(
            response.data["data"]["parsed"]["ack_type"],
            AcknowledgementType.X277,
        )

        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.UNDER_REVIEW)

        ack = EDIAcknowledgement.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(ack.ack_type, AcknowledgementType.X277)

    def test_import_277_denied_stc(self):
        content = (
            "ISA*00*          *00*          *ZZ*COMEDASSISTPROG*ZZ*89513013       "
            "*260817*1947*^*00501*000000001*0*T*:~"
            "GS*HN*COMEDASSISTPROG*89513013*20260817*1947*1*X*005010X214~"
            "ST*277*0001*005010X214~"
            "TRN*2*TRACK002~"
            "REF*D9*C-EDI-1~"
            "STC*A3:21:PR~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        response = self.client.post(
            reverse("edi-acknowledgement-import-277"),
            {
                "batch_id": self.batch.id,
                "content": content,
                "apply_claim_status": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["status"], "REJECTED")
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ClaimStatus.DENIED)
