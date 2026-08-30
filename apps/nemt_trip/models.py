from django.db import models

from apps.core.models import BaseModel


class NemtTripQuerySet(models.QuerySet):
    def with_relations(self):
        """Always join patient/provider to avoid N+1 on serializers/services."""
        return self.select_related("patient", "provider")


class NemtTrip(BaseModel):
    patient = models.ForeignKey(
        "patient.Patient",
        on_delete=models.PROTECT,
        related_name="nemt_trips",
        null=True,
        blank=True,
    )
    provider = models.ForeignKey(
        "provider_billing_profile.ProviderBillingProfile",
        on_delete=models.PROTECT,
        related_name="nemt_trips",
        null=True,
        blank=True,
    )
    service_date = models.DateField(null=True, blank=True)
    pickup = models.CharField(max_length=500, null=True, blank=True)
    dropoff = models.CharField(max_length=500, null=True, blank=True)
    one_way_miles = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    mileage_units = models.PositiveIntegerField(null=True, blank=True)
    charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    objects = NemtTripQuerySet.as_manager()

    class Meta:
        verbose_name = "NEMT Trip"
        verbose_name_plural = "NEMT Trips"
        ordering = ("-service_date", "-id")

    def __str__(self):
        date_label = self.service_date.isoformat() if self.service_date else "no-date"
        return f"Trip {self.pk} ({date_label})"
