"""Edifecs validation report import tests."""

from pathlib import Path

from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from apps.core.testing import AuthAPITestCase
from apps.edi.choices import ValidationReportStatus, ValidationReportType
from apps.edi.models import EDIValidationReport
from apps.edi.tests import EDIFixturesMixin
from apps.edi.utils.edifecs_report import parse_edifecs_report
from apps.edi.utils.service import create_edi_file_for_batch, import_validation_report

SAMPLE_DIR = Path(__file__).resolve().parent / "fixtures"


class ParseEdifecsReportTests(EDIFixturesMixin, TestCase):
    def test_parse_client_audit_xml(self):
        path = SAMPLE_DIR / "edifecs_audit_sample.xml"
        content = path.read_text(encoding="utf-8")
        parsed = parse_edifecs_report(content, file_name=path.name)
        self.assertEqual(parsed["report_type"], ValidationReportType.AUDIT)
        self.assertEqual(parsed["status"], ValidationReportStatus.PASSED)
        self.assertEqual(parsed["error_count"], 0)
        self.assertEqual(
            parsed["task_id"],
            "AF0E0DBA-F251-47E5-B287-0006F1B98603",
        )

    def test_parse_client_ldns_xml(self):
        path = SAMPLE_DIR / "edifecs_ldns_sample.xml"
        content = path.read_text(encoding="utf-8")
        parsed = parse_edifecs_report(content, file_name=path.name)
        self.assertEqual(parsed["report_type"], ValidationReportType.LDNS)
        self.assertEqual(parsed["status"], ValidationReportStatus.PASSED)
        self.assertEqual(parsed["accepted_claims"], 1)
        self.assertEqual(str(parsed["accepted_charge"]), "14.90")


class ValidationReportAPITests(EDIFixturesMixin, AuthAPITestCase):
    def _audit_xml(self):
        path = SAMPLE_DIR / "edifecs_audit_sample.xml"
        return path.read_text(encoding="utf-8")

    def test_import_validation_report_api(self):
        edi = create_edi_file_for_batch(
            batch_id=self.batch.id,
            file_hash="VALREP1",
            path_or_blob_ref="media/edi/837p.txt",
        )
        response = self.client.post(
            reverse("edi-validation-report-import"),
            {
                "batch_id": self.batch.id,
                "edi_file_id": edi.id,
                "content": self._audit_xml(),
                "file_name": "Report_Audit_sample.xml",
                "raw_file_ref": "s3://edi/reports/audit.xml",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["data"]["created"])
        self.assertEqual(response.data["data"]["report_type"], ValidationReportType.AUDIT)
        self.assertEqual(response.data["data"]["status"], ValidationReportStatus.PASSED.value)

        row = EDIValidationReport.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(row.batch_id, self.batch.id)
        self.assertEqual(row.edi_file_id, edi.id)

    def test_import_validation_report_idempotent(self):
        content = self._audit_xml()
        row1, _, created1 = import_validation_report(
            content=content,
            batch_id=self.batch.id,
            file_name="audit.xml",
        )
        self.assertTrue(created1)

        response = self.client.post(
            reverse("edi-validation-report-import"),
            {"content": content, "batch_id": self.batch.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["data"]["created"])
        self.assertEqual(response.data["data"]["id"], row1.id)

    def test_list_validation_reports(self):
        import_validation_report(
            content=self._audit_xml(),
            batch_id=self.batch.id,
            file_name="audit.xml",
        )
        response = self.client.get(
            reverse("edi-validation-report-list"),
            {"batch_id": self.batch.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 1)
