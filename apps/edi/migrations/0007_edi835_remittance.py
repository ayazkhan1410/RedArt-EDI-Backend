# Generated manually for EDI 835 remittance + claim payment lines.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("claim", "0003_edi_ack_and_attachment_submission"),
        ("edi", "0006_edi999import_and_tp_contact"),
    ]

    operations = [
        migrations.CreateModel(
            name="EDI835Remittance",
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
                    "file_hash",
                    models.CharField(
                        blank=True,
                        help_text="SHA-256 of normalized content for idempotent re-import.",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "raw_file_ref",
                    models.CharField(blank=True, max_length=1024, null=True),
                ),
                ("isa13", models.CharField(blank=True, max_length=16, null=True)),
                ("gs06", models.CharField(blank=True, max_length=16, null=True)),
                ("st02", models.CharField(blank=True, max_length=16, null=True)),
                (
                    "trace_number",
                    models.CharField(
                        blank=True,
                        help_text="TRN02 check / EFT trace number when present.",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "payment_method",
                    models.CharField(
                        blank=True,
                        help_text="BPR04 payment method code when present.",
                        max_length=8,
                        null=True,
                    ),
                ),
                (
                    "total_payment",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="BPR02 total provider payment amount.",
                        max_digits=14,
                        null=True,
                    ),
                ),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("message", models.CharField(blank=True, max_length=500, null=True)),
                ("claim_line_count", models.PositiveIntegerField(default=0)),
                ("applied_claim_count", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "EDI 835 Remittance",
                "verbose_name_plural": "EDI 835 Remittances",
                "ordering": ("-id",),
            },
        ),
        migrations.CreateModel(
            name="EDI835ClaimPayment",
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
                    "claim_number",
                    models.CharField(
                        help_text="CLP01 patient control / claim number.",
                        max_length=64,
                    ),
                ),
                (
                    "clp_status_code",
                    models.CharField(
                        help_text="CLP02 claim status code (1=paid primary, 4=denied, …).",
                        max_length=8,
                    ),
                ),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("PAID", "Paid"),
                            ("DENIED", "Denied"),
                            ("UNDER_REVIEW", "Under review"),
                            ("IGNORED", "Ignored / not applied"),
                        ],
                        default="IGNORED",
                        max_length=32,
                    ),
                ),
                (
                    "charge_amount",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                (
                    "payment_amount",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                (
                    "patient_responsibility",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                (
                    "payer_claim_control",
                    models.CharField(
                        blank=True,
                        help_text="CLP07 payer claim control number when present.",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "adjustment_codes",
                    models.CharField(
                        blank=True,
                        help_text="Compact CAS group/reason codes from following CAS segments.",
                        max_length=500,
                        null=True,
                    ),
                ),
                (
                    "prior_claim_status",
                    models.CharField(blank=True, max_length=32, null=True),
                ),
                (
                    "status_applied",
                    models.BooleanField(
                        default=False,
                        help_text="True when Claim.status was updated from this line.",
                    ),
                ),
                (
                    "skip_reason",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "claim",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="edi_835_payments",
                        to="claim.claim",
                    ),
                ),
                (
                    "remittance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="claim_payments",
                        to="edi.edi835remittance",
                    ),
                ),
            ],
            options={
                "verbose_name": "EDI 835 Claim Payment",
                "verbose_name_plural": "EDI 835 Claim Payments",
                "ordering": ("id",),
            },
        ),
        migrations.AddIndex(
            model_name="edi835remittance",
            index=models.Index(fields=["file_hash"], name="edi_835_file_hash_idx"),
        ),
        migrations.AddIndex(
            model_name="edi835remittance",
            index=models.Index(
                fields=["trace_number", "is_active"],
                name="edi_835_trace_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="edi835remittance",
            index=models.Index(
                fields=["isa13", "is_active"],
                name="edi_835_isa13_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="edi835claimpayment",
            index=models.Index(
                fields=["claim_number", "is_active"],
                name="edi_835_clm_num_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="edi835claimpayment",
            index=models.Index(
                fields=["outcome", "status_applied"],
                name="edi_835_outcome_applied_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="edi835claimpayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("remittance", "claim_number", "clp_status_code"),
                name="uniq_active_835_claim_line",
            ),
        ),
    ]
