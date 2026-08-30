from django.contrib import admin

from apps.claim.models import Claim


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "claim_number",
        "external_id",
        "trip",
        "diagnosis_code",
        "place_of_service",
        "total_charge",
        "status",
        "attachment_required",
        "attachment_status",
        "is_active",
        "created_at",
    )
    list_filter = (
        "status",
        "attachment_required",
        "attachment_status",
        "is_active",
        "created_at",
    )
    search_fields = (
        "claim_number",
        "external_id",
        "diagnosis_code",
        "trip__pickup",
        "trip__dropoff",
        "trip__patient__medicaid_member_id",
    )
    ordering = ("-id",)
    list_per_page = 50
    autocomplete_fields = ("trip",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "claim_number",
                    "external_id",
                    "trip",
                    "diagnosis_code",
                    "place_of_service",
                    "total_charge",
                    "status",
                    "is_active",
                )
            },
        ),
        (
            "Attachments",
            {
                "fields": (
                    "attachment_required",
                    "attachment_route",
                    "attachment_status",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
