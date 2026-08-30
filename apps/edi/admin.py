from django.contrib import admin

from apps.edi.models import EDIControlNumber, EDIFile


@admin.register(EDIControlNumber)
class EDIControlNumberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "batch",
        "environment",
        "isa13",
        "gs06",
        "is_active",
        "created_at",
    )
    list_filter = ("environment", "is_active")
    search_fields = ("isa13", "gs06", "batch__batch_number")
    autocomplete_fields = ("batch",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(EDIFile)
class EDIFileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "batch",
        "transaction_type",
        "filename",
        "status",
        "uploaded_at",
        "is_active",
        "created_at",
    )
    list_filter = ("transaction_type", "status", "is_active")
    search_fields = ("filename", "file_hash", "path_or_blob_ref", "batch__batch_number")
    autocomplete_fields = ("batch", "control_number")
    readonly_fields = ("id", "created_at", "updated_at")
