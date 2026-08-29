from django.db import models

from apps.core.models import BaseModel


class ProviderBillingProfile(BaseModel):
    legal_name = models.CharField(max_length=300, blank=True, null=True)
    billing_name = models.CharField(max_length=300, blank=True, null=True)
    npi = models.CharField(max_length=50, blank=True, null=True)
    taxonomy_code = models.CharField(max_length=50, blank=True, null=True)
    location_id = models.CharField(max_length=50, blank=True, null=True)
    medicaid_provider_id = models.CharField(max_length=50, blank=True, null=True)
    revalidation_date = models.DateField(blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    zip = models.CharField(max_length=50, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    address_line_1 = models.CharField(max_length=500, blank=True, null=True)
    address_line_2 = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Provider Billing Profile"
        verbose_name_plural = "Provider Billing Profiles"

    def __str__(self):
        return self.billing_name or self.legal_name or str(self.pk)
