from django.db import models

from apps.claim.choices import AttachmentRoute, AttachmentStatus, ClaimStatus
from apps.core.models import BaseModel


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
            # List/filter by workflow status at scale
            models.Index(fields=["status"], name="claim_status_idx"),
            models.Index(
                fields=["attachment_required", "attachment_status"],
                name="claim_attach_flags_idx",
            ),
        ]

    def __str__(self):
        return self.claim_number or f"Claim {self.pk}"
