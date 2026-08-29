from django.contrib import admin

from apps.trading_partner.models import TradingPartner


@admin.register(TradingPartner)
class TradingPartnerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "sender_id",
        "receiver_id",
        "environment",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("environment", "is_active", "created_at")
    search_fields = ("name", "sender_id", "receiver_id")
    ordering = ("-id",)
    list_per_page = 50
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "name",
                    "sender_id",
                    "receiver_id",
                    "environment",
                    "is_active",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )
