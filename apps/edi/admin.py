from django.contrib import admin

from apps.edi.models import (
    EDI999Import,
    EDI835ClaimPayment,
    EDI835Remittance,
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


@admin.register(EDI999Import)
class EDI999ImportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "filename",
        "status",
        "credentials",
        "batch",
        "acknowledgement",
        "attempt",
        "celery_task_id",
        "is_active",
        "created_at",
    )
    list_filter = ("status", "is_active")
    search_fields = (
        "filename",
        "remote_path",
        "file_hash",
        "celery_task_id",
        "message",
    )
    autocomplete_fields = (
        "credentials",
        "directory",
        "batch",
        "edi_file",
        "acknowledgement",
    )
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "finished_at")


class EDI835ClaimPaymentInline(admin.TabularInline):
    model = EDI835ClaimPayment
    extra = 0
    readonly_fields = (
        "id",
        "claim",
        "claim_number",
        "clp_status_code",
        "outcome",
        "payment_amount",
        "status_applied",
        "skip_reason",
        "created_at",
    )
    can_delete = False


@admin.register(EDI835Remittance)
class EDI835RemittanceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trace_number",
        "total_payment",
        "payment_date",
        "claim_line_count",
        "applied_claim_count",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "payment_method")
    search_fields = ("file_hash", "trace_number", "isa13", "raw_file_ref", "message")
    readonly_fields = ("id", "created_at", "updated_at", "file_hash")
    inlines = [EDI835ClaimPaymentInline]


@admin.register(EDI835ClaimPayment)
class EDI835ClaimPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "remittance",
        "claim_number",
        "claim",
        "clp_status_code",
        "outcome",
        "payment_amount",
        "status_applied",
        "is_active",
    )
    list_filter = ("outcome", "status_applied", "is_active")
    search_fields = ("claim_number", "payer_claim_control", "adjustment_codes")
    autocomplete_fields = ("remittance", "claim")
    readonly_fields = ("id", "created_at", "updated_at")
