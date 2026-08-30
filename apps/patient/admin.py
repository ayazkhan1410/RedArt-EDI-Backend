from django.contrib import admin

from apps.patient.models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "medicaid_member_id",
        "gender",
        "county",
        "city",
        "state",
        "date_of_birth",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "gender", "county", "state", "created_at")
    search_fields = (
        "first_name",
        "last_name",
        "medicaid_member_id",
        "county",
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
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "gender",
                    "medicaid_member_id",
                    "county",
                    "email",
                    "phone",
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
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
