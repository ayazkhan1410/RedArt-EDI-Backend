# Generated manually — Edifecs validation reports

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edi", "0009_edi835remittance_file_hash_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="EDIValidationReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "report_type",
                    models.CharField(
                        choices=[
                            ("SUMMARY", "Summary / audit summary"),
                            ("AUDIT", "Audit report"),
                            ("LDNS", "Long-distance / data validation"),
                        ],
                        default="SUMMARY",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PASSED", "Passed"),
                            ("ACCEPTED", "Accepted"),
                            ("FAILED", "Failed"),
                            ("REJECTED", "Rejected"),
                            ("PARTIAL", "Partial"),
                            ("ERROR", "Error"),
                            ("UNKNOWN", "Unknown"),
                        ],
                        default="UNKNOWN",
                        max_length=32,
                    ),
                ),
                ("task_id", models.CharField(blank=True, max_length=128, null=True)),
                ("report_guid", models.CharField(blank=True, max_length=64, null=True)),
                ("file_name", models.CharField(blank=True, max_length=255, null=True)),
                ("file_hash", models.CharField(blank=True, max_length=128, null=True)),
                ("error_count", models.PositiveIntegerField(blank=True, default=0, null=True)),
                ("accepted_claims", models.PositiveIntegerField(blank=True, null=True)),
                ("accepted_charge", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("raw_file_ref", models.CharField(blank=True, max_length=1024, null=True)),
                ("message", models.CharField(blank=True, max_length=500, null=True)),
                ("parsed_summary", models.JSONField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="validation_reports",
                        to="claim.submissionbatch",
                    ),
                ),
                (
                    "edi_file",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="validation_reports",
                        to="edi.edifile",
                    ),
                ),
            ],
            options={
                "verbose_name": "EDI Validation Report",
                "verbose_name_plural": "EDI Validation Reports",
                "ordering": ("-id",),
                "indexes": [
                    models.Index(fields=["task_id"], name="edi_valrep_task_idx"),
                    models.Index(
                        fields=["report_type", "status"],
                        name="edi_valrep_type_status_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("file_hash__isnull", False), ("is_active", True)),
                        fields=("file_hash",),
                        name="uniq_active_validation_report_hash",
                    ),
                ],
            },
        ),
    ]
