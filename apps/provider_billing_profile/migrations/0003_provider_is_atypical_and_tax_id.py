"""
Migration: add is_atypical and tax_id fields to ProviderBillingProfile.

is_atypical — True for Colorado Medicaid atypical providers that have no NPI.
              Uses medicaid_provider_id with NM108=1C in the 837P.
              False (default) for standard NPI providers.

tax_id      — EIN/TIN required for the 837P REF*EI segment when NM108=XX (NPI).
              Stored as digits only; supplied by the company during onboarding.
              Must never be hard-coded or defaulted from settings.

Both fields are nullable/optional at the DB level; the 837P readiness validator
enforces the right combination before generation.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("provider_billing_profile", "0002_providerbillingprofile_location_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="providerbillingprofile",
            name="is_atypical",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "True = atypical Colorado Medicaid provider without NPI. "
                    "Uses medicaid_provider_id (NM108=1C) in the 837P."
                ),
            ),
        ),
        migrations.AddField(
            model_name="providerbillingprofile",
            name="tax_id",
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                help_text=(
                    "EIN or TIN (digits only). "
                    "Required for NPI providers in 837P REF*EI. "
                    "Never hard-coded; supplied by the company during onboarding."
                ),
            ),
        ),
    ]
