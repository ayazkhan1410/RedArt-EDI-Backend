from django.db import models

from apps.claim.choices import (
    AttachmentRoute,
    AttachmentStatus,
    BatchStatus,
    ClaimStatus,
    DocumentStatus,
    DocumentType,
)
from apps.core.models import BaseModel
from apps.trading_partner.choices import Environment


class ClaimQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "trip",
            "trip__patient",
            "trip__provider",
        )


class Claim(BaseModel):
    claim_number = models.CharField(max_length=64, null=True, blank=True)
    external_id = models.CharField(max_length=128, null=True, blank=True)
    trip = models.ForeignKey(
        "nemt_trip.NemtTrip",
        on_delete=models.PROTECT,
        related_name="claims",
        null=True,
        blank=True,
    )
    diagnosis_code = models.CharField(max_length=32, null=True, blank=True)
    place_of_service = models.CharField(max_length=16, null=True, blank=True)
    total_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=ClaimStatus.choices,
        default=ClaimStatus.DRAFT,
        null=True,
        blank=True,
    )
    attachment_required = models.BooleanField(default=False)
    attachment_route = models.CharField(
        max_length=64,
        choices=AttachmentRoute.choices,
        default=AttachmentRoute.NONE,
        null=True,
        blank=True,
    )
    attachment_status = models.CharField(
        max_length=32,
        choices=AttachmentStatus.choices,
        default=AttachmentStatus.NOT_REQUIRED,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    objects = ClaimQuerySet.as_manager()

    class Meta:
        verbose_name = "Claim"
        verbose_name_plural = "Claims"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["claim_number"],
                condition=models.Q(claim_number__isnull=False),
                name="uniq_claim_claim_number_not_null",
            ),
            models.UniqueConstraint(
                fields=["external_id"],
                condition=models.Q(external_id__isnull=False),
                name="uniq_claim_external_id_not_null",
            ),
            models.UniqueConstraint(
                fields=["trip"],
                condition=models.Q(trip__isnull=False),
                name="uniq_claim_trip_not_null",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="claim_status_idx"),
            models.Index(
                fields=["attachment_required", "attachment_status"],
                name="claim_attach_flags_idx",
            ),
        ]

    def __str__(self):
        return self.claim_number or f"Claim {self.pk}"


class ClaimDocumentQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "claim",
            "claim__trip",
            "claim__trip__patient",
            "claim__trip__provider",
        )


class ClaimDocument(BaseModel):
    claim = models.ForeignKey(
        Claim,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    document_type = models.CharField(
        max_length=64,
        choices=DocumentType.choices,
        null=True,
        blank=True,
    )
    file_name = models.CharField(max_length=255, null=True, blank=True)
    document_hash = models.CharField(max_length=128, null=True, blank=True)
    is_signed = models.BooleanField(default=False)
    status = models.CharField(
        max_length=32,
        choices=DocumentStatus.choices,
        default=DocumentStatus.PENDING,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    objects = ClaimDocumentQuerySet.as_manager()

    class Meta:
        verbose_name = "Claim Document"
        verbose_name_plural = "Claim Documents"
        ordering = ("claim_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["claim", "document_type"],
                condition=models.Q(
                    claim__isnull=False,
                    document_type__isnull=False,
                    is_active=True,
                ),
                name="uniq_active_claim_document_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=["claim", "status"],
                name="claim_doc_claim_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.document_type or 'DOC'} #{self.pk}"


class SubmissionBatchQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related("trading_partner")


class SubmissionBatch(BaseModel):
    batch_number = models.CharField(max_length=64, null=True, blank=True)
    trading_partner = models.ForeignKey(
        "trading_partner.TradingPartner",
        on_delete=models.PROTECT,
        related_name="submission_batches",
        null=True,
        blank=True,
    )
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.TEST,
    )
    claim_count = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=BatchStatus.choices,
        default=BatchStatus.DRAFT,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    objects = SubmissionBatchQuerySet.as_manager()

    class Meta:
        verbose_name = "Submission Batch"
        verbose_name_plural = "Submission Batches"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["batch_number"],
                condition=models.Q(batch_number__isnull=False),
                name="uniq_submission_batch_number_not_null",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="submission_batch_status_idx"),
            models.Index(
                fields=["environment", "is_active"],
                name="submission_batch_env_idx",
            ),
        ]

    def __str__(self):
        return self.batch_number or f"Batch {self.pk}"


class BatchClaimQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "batch",
            "batch__trading_partner",
            "claim",
            "claim__trip",
            "claim__trip__patient",
            "claim__trip__provider",
        )


class BatchClaim(BaseModel):
    batch = models.ForeignKey(
        SubmissionBatch,
        on_delete=models.CASCADE,
        related_name="batch_claims",
        null=True,
        blank=True,
    )
    claim = models.ForeignKey(
        Claim,
        on_delete=models.PROTECT,
        related_name="batch_claims",
        null=True,
        blank=True,
    )
    st02 = models.CharField(max_length=16, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = BatchClaimQuerySet.as_manager()

    class Meta:
        verbose_name = "Batch Claim"
        verbose_name_plural = "Batch Claims"
        ordering = ("batch_id", "st02", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "claim"],
                condition=models.Q(batch__isnull=False, claim__isnull=False),
                name="uniq_batch_claim_pair",
            ),
            models.UniqueConstraint(
                fields=["batch", "st02"],
                condition=models.Q(
                    batch__isnull=False,
                    st02__isnull=False,
                ),
                name="uniq_batch_st02",
            ),
        ]

    def __str__(self):
        return f"BatchClaim {self.pk} (ST02={self.st02})"
