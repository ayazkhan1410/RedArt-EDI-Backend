from django.contrib import admin

from apps.patient.models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "medicaid_member_id",
        "county",
        "date_of_birth",
        "email",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active", "county", "created_at")
    search_fields = (
        "first_name",
        "last_name",
        "medicaid_member_id",
        "county",
        "email",
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
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "medicaid_member_id",
                    "county",
                    "email",
                    "is_active",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )
