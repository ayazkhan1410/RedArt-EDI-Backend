from django.contrib import admin

from apps.provider_billing_profile.models import ProviderBillingProfile


@admin.register(ProviderBillingProfile)
class ProviderBillingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "legal_name",
        "billing_name",
        "npi",
        "medicaid_provider_id",
        "city",
        "state",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active", "state", "country", "created_at")
    search_fields = (
        "legal_name",
        "billing_name",
        "npi",
        "medicaid_provider_id",
        "city",
        "email",
        "phone",
    )
    ordering = ("-id",)
    list_per_page = 50
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "legal_name",
                    "billing_name",
                    "npi",
                    "taxonomy_code",
                    "medicaid_provider_id",
                    "is_active",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "zip",
                    "country",
                )
            },
        ),
        (
            "Contact",
            {"fields": ("phone", "email")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )
