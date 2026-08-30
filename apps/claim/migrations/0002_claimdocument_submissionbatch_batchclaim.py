# Generated manually for ClaimDocument / SubmissionBatch / BatchClaim

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("claim", "0001_initial"),
        ("trading_partner", "0003_remove_extra_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClaimDocument",
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
                    "document_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("STANDARD_TRIP_LOG", "Standard trip log"),
                            ("MILE_25_VERIFICATION", "25+ mile verification"),
                            ("OTHER", "Other"),
                        ],
                        max_length=64,
                        null=True,
                    ),
                ),
                ("file_name", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "document_hash",
                    models.CharField(blank=True, max_length=128, null=True),
                ),
                ("is_signed", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("MISSING", "Missing"),
                            ("PENDING", "Pending"),
                            ("COMPLETE", "Complete"),
                        ],
                        default="PENDING",
                        max_length=32,
                        null=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "claim",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="claim.claim",
                    ),
                ),
            ],
            options={
                "verbose_name": "Claim Document",
                "verbose_name_plural": "Claim Documents",
                "ordering": ("claim_id", "id"),
            },
        ),
        migrations.CreateModel(
            name="SubmissionBatch",
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
                    "batch_number",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                (
                    "environment",
                    models.CharField(
                        choices=[("TEST", "Test"), ("PRODUCTION", "Production")],
                        default="TEST",
                        max_length=20,
                    ),
                ),
                ("claim_count", models.PositiveIntegerField(default=0)),
                (
                    "total_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("DRAFT", "Draft"),
                            ("READY", "Ready"),
                            ("GENERATED", "837P generated"),
                            ("SUBMITTED", "Submitted"),
                            ("ACKNOWLEDGED", "Acknowledged"),
                            ("FAILED", "Failed"),
                        ],
                        default="DRAFT",
                        max_length=32,
                        null=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "trading_partner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="submission_batches",
                        to="trading_partner.tradingpartner",
                    ),
                ),
            ],
            options={
                "verbose_name": "Submission Batch",
                "verbose_name_plural": "Submission Batches",
                "ordering": ("-id",),
            },
        ),
        migrations.CreateModel(
            name="BatchClaim",
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
                ("st02", models.CharField(blank=True, max_length=16, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="batch_claims",
                        to="claim.submissionbatch",
                    ),
                ),
                (
                    "claim",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="batch_claims",
                        to="claim.claim",
                    ),
                ),
            ],
            options={
                "verbose_name": "Batch Claim",
                "verbose_name_plural": "Batch Claims",
                "ordering": ("batch_id", "st02", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="claimdocument",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("claim__isnull", False),
                    ("document_type__isnull", False),
                    ("is_active", True),
                ),
                fields=("claim", "document_type"),
                name="uniq_active_claim_document_type",
            ),
        ),
        migrations.AddIndex(
            model_name="claimdocument",
            index=models.Index(
                fields=["claim", "status"],
                name="claim_doc_claim_status_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="submissionbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("batch_number__isnull", False)),
                fields=("batch_number",),
                name="uniq_submission_batch_number_not_null",
            ),
        ),
        migrations.AddIndex(
            model_name="submissionbatch",
            index=models.Index(fields=["status"], name="submission_batch_status_idx"),
        ),
        migrations.AddIndex(
            model_name="submissionbatch",
            index=models.Index(
                fields=["environment", "is_active"],
                name="submission_batch_env_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="batchclaim",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("batch__isnull", False),
                    ("claim__isnull", False),
                ),
                fields=("batch", "claim"),
                name="uniq_batch_claim_pair",
            ),
        ),
        migrations.AddConstraint(
            model_name="batchclaim",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("batch__isnull", False),
                    ("st02__isnull", False),
                ),
                fields=("batch", "st02"),
                name="uniq_batch_st02",
            ),
        ),
    ]
