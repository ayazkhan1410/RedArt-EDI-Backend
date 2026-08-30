from django.db import models

from apps.core.models import BaseModel
from apps.edi.choices import EDIFileStatus, TransactionType
from apps.trading_partner.choices import Environment


class EDIControlNumberQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "batch",
            "batch__trading_partner",
        )


class EDIControlNumber(BaseModel):
    """
    X12 interchange / functional-group control numbers for a submission batch.
    Reconcile with BatchClaim.st02 (transaction set control number).
    """

    batch = models.ForeignKey(
        "claim.SubmissionBatch",
        on_delete=models.PROTECT,
        related_name="edi_control_numbers",
        null=True,
        blank=True,
    )
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.TEST,
    )
    isa13 = models.CharField(
        max_length=9,
        null=True,
        blank=True,
        help_text="ISA13 interchange control number (typically 9 digits).",
    )
    gs06 = models.CharField(
        max_length=9,
        null=True,
        blank=True,
        help_text="GS06 group control number.",
    )
    is_active = models.BooleanField(default=True)

    objects = EDIControlNumberQuerySet.as_manager()

    class Meta:
        verbose_name = "EDI Control Number"
        verbose_name_plural = "EDI Control Numbers"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["batch"],
                condition=models.Q(batch__isnull=False, is_active=True),
                name="uniq_active_edi_control_per_batch",
            ),
            models.UniqueConstraint(
                fields=["environment", "isa13"],
                condition=models.Q(
                    environment__isnull=False,
                    isa13__isnull=False,
                    is_active=True,
                ),
                name="uniq_active_isa13_per_environment",
            ),
            models.UniqueConstraint(
                fields=["environment", "gs06"],
                condition=models.Q(
                    environment__isnull=False,
                    gs06__isnull=False,
                    is_active=True,
                ),
                name="uniq_active_gs06_per_environment",
            ),
        ]
        indexes = [
            models.Index(
                fields=["environment", "is_active"],
                name="edi_ctrl_env_active_idx",
            ),
        ]

    def __str__(self):
        return f"ISA13={self.isa13} GS06={self.gs06} ({self.environment})"


class EDIFileQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "batch",
            "batch__trading_partner",
            "control_number",
        )


class EDIFile(BaseModel):
    """
    Generated / uploaded X12 file for a batch.
    Transport status only — do not mirror Claim.status here.
    """

    batch = models.ForeignKey(
        "claim.SubmissionBatch",
        on_delete=models.PROTECT,
        related_name="edi_files",
        null=True,
        blank=True,
    )
    control_number = models.ForeignKey(
        EDIControlNumber,
        on_delete=models.SET_NULL,
        related_name="edi_files",
        null=True,
        blank=True,
    )
    transaction_type = models.CharField(
        max_length=16,
        choices=TransactionType.choices,
        default=TransactionType.X837P,
        null=True,
        blank=True,
    )
    filename = models.CharField(max_length=255, null=True, blank=True)
    file_hash = models.CharField(max_length=128, null=True, blank=True)
    path_or_blob_ref = models.CharField(max_length=1024, null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=EDIFileStatus.choices,
        default=EDIFileStatus.GENERATED,
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = EDIFileQuerySet.as_manager()

    class Meta:
        verbose_name = "EDI File"
        verbose_name_plural = "EDI Files"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["filename"],
                condition=models.Q(filename__isnull=False),
                name="uniq_edi_file_filename_not_null",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="edi_file_status_idx"),
            models.Index(
                fields=["batch", "transaction_type"],
                name="edi_file_batch_txn_idx",
            ),
        ]

    def __str__(self):
        return self.filename or f"EDIFile {self.pk}"
