from django.contrib import admin

from apps.edi.models import (
    EDIAcknowledgement,
    EDIControlNumber,
    EDIFile,
    EDIFileTransferLog,
    SFTPCredentials,
    SFTPDirectory,
)


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


@admin.register(EDIFileTransferLog)
class EDIFileTransferLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "edi_file",
        "channel",
        "status",
        "attempt",
        "remote_path",
        "celery_task_id",
        "started_at",
        "finished_at",
        "is_active",
    )
    list_filter = ("channel", "status", "is_active")
    search_fields = (
        "message",
        "remote_path",
        "celery_task_id",
        "edi_file__filename",
    )
    autocomplete_fields = ("edi_file",)
    readonly_fields = ("id", "created_at", "updated_at", "detail")


@admin.register(EDIAcknowledgement)
class EDIAcknowledgementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "batch",
        "edi_file",
        "ack_type",
        "status",
        "affected_st02",
        "raw_file_ref",
        "acknowledged_at",
        "is_active",
        "created_at",
    )
    list_filter = ("ack_type", "status", "is_active")
    search_fields = (
        "affected_st02",
        "raw_file_ref",
        "message",
        "batch__batch_number",
    )
    autocomplete_fields = ("batch", "edi_file")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SFTPCredentials)
class SFTPCredentialsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "environment",
        "host",
        "port",
        "username",
        "auth_type",
        "trading_partner",
        "is_active",
        "created_at",
    )
    list_filter = ("environment", "auth_type", "is_active")
    search_fields = ("name", "host", "username")
    autocomplete_fields = ("trading_partner",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "name",
                    "trading_partner",
                    "environment",
                    "host",
                    "port",
                    "username",
                    "auth_type",
                    "timeout_seconds",
                    "host_fingerprint",
                    "notes",
                    "is_active",
                )
            },
        ),
        (
            "Secrets",
            {
                "classes": ("collapse",),
                "fields": ("password", "private_key_pem", "private_key_passphrase"),
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(SFTPDirectory)
class SFTPDirectoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "credentials",
        "purpose",
        "sending_path",
        "receiving_path",
        "is_active",
        "created_at",
    )
    list_filter = ("purpose", "is_active")
    search_fields = ("name", "sending_path", "receiving_path", "credentials__name")
    autocomplete_fields = ("credentials",)
    readonly_fields = ("id", "created_at", "updated_at")
