# Generated manually for EDIControlNumber + EDIFile

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("claim", "0002_claimdocument_submissionbatch_batchclaim"),
    ]

    operations = [
        migrations.CreateModel(
            name="EDIControlNumber",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "environment",
                    models.CharField(
                        choices=[("TEST", "Test"), ("PRODUCTION", "Production")],
                        default="TEST",
                        max_length=20,
                    ),
                ),
                (
                    "isa13",
                    models.CharField(
                        blank=True,
                        help_text="ISA13 interchange control number (typically 9 digits).",
                        max_length=9,
                        null=True,
                    ),
                ),
                (
                    "gs06",
                    models.CharField(
                        blank=True,
                        help_text="GS06 group control number.",
                        max_length=9,
                        null=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="edi_control_numbers",
                        to="claim.submissionbatch",
                    ),
                ),
            ],
            options={
                "verbose_name": "EDI Control Number",
                "verbose_name_plural": "EDI Control Numbers",
                "ordering": ("-id",),
            },
        ),
        migrations.CreateModel(
            name="EDIFile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "transaction_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("837P", "837 Professional"),
                            ("999", "Implementation Acknowledgment"),
                            ("277", "Claim Status"),
                            ("OTHER", "Other"),
                        ],
                        default="837P",
                        max_length=16,
                        null=True,
                    ),
                ),
                ("filename", models.CharField(blank=True, max_length=255, null=True)),
                ("file_hash", models.CharField(blank=True, max_length=128, null=True)),
                (
                    "path_or_blob_ref",
                    models.CharField(blank=True, max_length=1024, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("GENERATED", "Generated"),
                            ("UPLOADED", "Uploaded"),
                            ("ACKNOWLEDGED", "Acknowledged"),
                            ("FAILED", "Failed"),
                            ("ARCHIVED", "Archived"),
                        ],
                        default="GENERATED",
                        max_length=32,
                        null=True,
                    ),
                ),
                ("uploaded_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="edi_files",
                        to="claim.submissionbatch",
                    ),
                ),
                (
                    "control_number",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="edi_files",
                        to="edi.edicontrolnumber",
                    ),
                ),
            ],
            options={
                "verbose_name": "EDI File",
                "verbose_name_plural": "EDI Files",
                "ordering": ("-id",),
            },
        ),
        migrations.AddConstraint(
            model_name="edicontrolnumber",
            constraint=models.UniqueConstraint(
                condition=models.Q(("batch__isnull", False), ("is_active", True)),
                fields=("batch",),
                name="uniq_active_edi_control_per_batch",
            ),
        ),
        migrations.AddConstraint(
            model_name="edicontrolnumber",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("environment__isnull", False),
                    ("isa13__isnull", False),
                    ("is_active", True),
                ),
                fields=("environment", "isa13"),
                name="uniq_active_isa13_per_environment",
            ),
        ),
        migrations.AddConstraint(
            model_name="edicontrolnumber",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("environment__isnull", False),
                    ("gs06__isnull", False),
                    ("is_active", True),
                ),
                fields=("environment", "gs06"),
                name="uniq_active_gs06_per_environment",
            ),
        ),
        migrations.AddIndex(
            model_name="edicontrolnumber",
            index=models.Index(
                fields=["environment", "is_active"],
                name="edi_ctrl_env_active_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="edifile",
            constraint=models.UniqueConstraint(
                condition=models.Q(("filename__isnull", False)),
                fields=("filename",),
                name="uniq_edi_file_filename_not_null",
            ),
        ),
        migrations.AddIndex(
            model_name="edifile",
            index=models.Index(fields=["status"], name="edi_file_status_idx"),
        ),
        migrations.AddIndex(
            model_name="edifile",
            index=models.Index(
                fields=["batch", "transaction_type"],
                name="edi_file_batch_txn_idx",
            ),
        ),
    ]
