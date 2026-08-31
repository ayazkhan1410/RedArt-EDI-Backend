from django.db import models

from apps.core.models import BaseModel
from apps.edi.choices import (
    AcknowledgementStatus,
    AcknowledgementType,
    EDI999ImportStatus,
    EDIFileStatus,
    SFTPAuthType,
    SFTPDirectoryPurpose,
    TransactionType,
    TransferChannel,
    TransferLogStatus,
)
from apps.trading_partner.choices import Environment


class EDIControlNumberQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "batch",
            "batch__trading_partner",
        )


class EDIControlNumber(BaseModel):
    """
    X12 interchange / functional-group control numbers for a submission batch.
    Reconcile with BatchClaim.st02 (transaction set control number).
    """

    batch = models.ForeignKey(
        "claim.SubmissionBatch",
        on_delete=models.PROTECT,
        related_name="edi_control_numbers",
        null=True,
        blank=True,
    )
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.TEST,
    )
    isa13 = models.CharField(
        max_length=9,
        null=True,
        blank=True,
        help_text="ISA13 interchange control number (typically 9 digits).",
    )
    gs06 = models.CharField(
        max_length=9,
        null=True,
        blank=True,
        help_text="GS06 group control number.",
    )
    is_active = models.BooleanField(default=True)

    objects = EDIControlNumberQuerySet.as_manager()

    class Meta:
        verbose_name = "EDI Control Number"
        verbose_name_plural = "EDI Control Numbers"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["batch"],
                condition=models.Q(batch__isnull=False, is_active=True),
                name="uniq_active_edi_control_per_batch",
            ),
            models.UniqueConstraint(
                fields=["environment", "isa13"],
                condition=models.Q(
                    environment__isnull=False,
                    isa13__isnull=False,
                    is_active=True,
                ),
                name="uniq_active_isa13_per_environment",
            ),
            models.UniqueConstraint(
                fields=["environment", "gs06"],
                condition=models.Q(
                    environment__isnull=False,
                    gs06__isnull=False,
                    is_active=True,
                ),
                name="uniq_active_gs06_per_environment",
            ),
        ]
        indexes = [
            models.Index(
                fields=["environment", "is_active"],
                name="edi_ctrl_env_active_idx",
            ),
        ]

    def __str__(self):
        return f"ISA13={self.isa13} GS06={self.gs06} ({self.environment})"


class EDIFileQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "batch",
            "batch__trading_partner",
            "control_number",
        )


class EDIFile(BaseModel):
    """
    Generated / uploaded X12 file for a batch.
    Transport status only — do not mirror Claim.status here.
    """

    batch = models.ForeignKey(
        "claim.SubmissionBatch",
        on_delete=models.PROTECT,
        related_name="edi_files",
        null=True,
        blank=True,
    )
    control_number = models.ForeignKey(
        EDIControlNumber,
        on_delete=models.SET_NULL,
        related_name="edi_files",
        null=True,
        blank=True,
    )
    transaction_type = models.CharField(
        max_length=16,
        choices=TransactionType.choices,
        default=TransactionType.X837P,
        null=True,
        blank=True,
    )
    filename = models.CharField(max_length=255, null=True, blank=True)
    file_hash = models.CharField(max_length=128, null=True, blank=True)
    path_or_blob_ref = models.CharField(max_length=1024, null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=EDIFileStatus.choices,
        default=EDIFileStatus.GENERATED,
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = EDIFileQuerySet.as_manager()

    class Meta:
        verbose_name = "EDI File"
        verbose_name_plural = "EDI Files"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["filename"],
                condition=models.Q(filename__isnull=False),
                name="uniq_edi_file_filename_not_null",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="edi_file_status_idx"),
            models.Index(
                fields=["batch", "transaction_type"],
                name="edi_file_batch_txn_idx",
            ),
        ]

    def __str__(self):
        return self.filename or f"EDIFile {self.pk}"


class EDIFileTransferLogQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "edi_file",
            "edi_file__batch",
            "edi_file__batch__trading_partner",
        )


class EDIFileTransferLog(BaseModel):
    """
    Per-channel upload attempt trail (SFTP / S3) for FE and ops.
    One EDIFile can have many log rows across retries.
    """

    edi_file = models.ForeignKey(
        EDIFile,
        on_delete=models.CASCADE,
        related_name="transfer_logs",
    )
    channel = models.CharField(
        max_length=16,
        choices=TransferChannel.choices,
    )
    status = models.CharField(
        max_length=32,
        choices=TransferLogStatus.choices,
        default=TransferLogStatus.PENDING,
    )
    attempt = models.PositiveIntegerField(default=1)
    remote_path = models.CharField(max_length=1024, null=True, blank=True)
    message = models.CharField(max_length=500, null=True, blank=True)
    detail = models.TextField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = EDIFileTransferLogQuerySet.as_manager()

    class Meta:
        verbose_name = "EDI File Transfer Log"
        verbose_name_plural = "EDI File Transfer Logs"
        ordering = ("-id",)
        indexes = [
            models.Index(
                fields=["edi_file", "channel"],
                name="edi_xfer_file_channel_idx",
            ),
            models.Index(
                fields=["status", "is_active"],
                name="edi_xfer_status_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.channel} {self.status} #{self.pk}"


class EDIAcknowledgementQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "batch",
            "batch__trading_partner",
            "edi_file",
            "edi_file__batch",
        )


class EDIAcknowledgement(BaseModel):
    """
    Inbound acknowledgement (typically 999) for a submission batch / ST02.
    ACCEPTED means structural accept of the EDI — not payment.
    """

    batch = models.ForeignKey(
        "claim.SubmissionBatch",
        on_delete=models.PROTECT,
        related_name="edi_acknowledgements",
        null=True,
        blank=True,
    )
    edi_file = models.ForeignKey(
        EDIFile,
        on_delete=models.SET_NULL,
        related_name="acknowledgements",
        null=True,
        blank=True,
    )
    ack_type = models.CharField(
        max_length=16,
        choices=AcknowledgementType.choices,
        default=AcknowledgementType.X999,
    )
    status = models.CharField(
        max_length=32,
        choices=AcknowledgementStatus.choices,
        default=AcknowledgementStatus.ACCEPTED,
    )
    affected_st02 = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        help_text="Transaction set control number (ST02) affected by this ack.",
    )
    raw_file_ref = models.CharField(max_length=1024, null=True, blank=True)
    message = models.CharField(max_length=500, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = EDIAcknowledgementQuerySet.as_manager()

    class Meta:
        verbose_name = "EDI Acknowledgement"
        verbose_name_plural = "EDI Acknowledgements"
        ordering = ("-id",)
        indexes = [
            models.Index(
                fields=["batch", "ack_type"],
                name="edi_ack_batch_type_idx",
            ),
            models.Index(
                fields=["status", "is_active"],
                name="edi_ack_status_active_idx",
            ),
            models.Index(
                fields=["affected_st02"],
                name="edi_ack_st02_idx",
            ),
        ]

    def __str__(self):
        return f"{self.ack_type} {self.status} ST02={self.affected_st02} #{self.pk}"


class EDI999ImportQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "credentials",
            "credentials__trading_partner",
            "directory",
            "acknowledgement",
            "acknowledgement__batch",
            "batch",
            "edi_file",
        )


class EDI999Import(BaseModel):
    """
    Track one inbound 999 file discovered on SFTP through import outcome.
    Idempotent on credentials + remote_path (and file_hash when set).
    """

    credentials = models.ForeignKey(
        "edi.SFTPCredentials",
        on_delete=models.PROTECT,
        related_name="edi_999_imports",
        null=True,
        blank=True,
    )
    directory = models.ForeignKey(
        "edi.SFTPDirectory",
        on_delete=models.SET_NULL,
        related_name="edi_999_imports",
        null=True,
        blank=True,
    )
    batch = models.ForeignKey(
        "claim.SubmissionBatch",
        on_delete=models.SET_NULL,
        related_name="edi_999_imports",
        null=True,
        blank=True,
    )
    edi_file = models.ForeignKey(
        EDIFile,
        on_delete=models.SET_NULL,
        related_name="edi_999_imports",
        null=True,
        blank=True,
    )
    acknowledgement = models.ForeignKey(
        EDIAcknowledgement,
        on_delete=models.SET_NULL,
        related_name="import_rows",
        null=True,
        blank=True,
    )
    filename = models.CharField(max_length=255)
    remote_path = models.CharField(max_length=1024)
    file_hash = models.CharField(max_length=128, null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=EDI999ImportStatus.choices,
        default=EDI999ImportStatus.DISCOVERED,
    )
    attempt = models.PositiveIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    message = models.CharField(max_length=500, null=True, blank=True)
    detail = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = EDI999ImportQuerySet.as_manager()

    class Meta:
        verbose_name = "EDI 999 Import"
        verbose_name_plural = "EDI 999 Imports"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["credentials", "remote_path"],
                condition=models.Q(
                    credentials__isnull=False,
                    remote_path__isnull=False,
                    is_active=True,
                ),
                name="uniq_active_edi_999_import_remote_path",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "is_active"],
                name="edi_999_imp_status_active_idx",
            ),
            models.Index(
                fields=["file_hash"],
                name="edi_999_imp_hash_idx",
            ),
            models.Index(
                fields=["filename"],
                name="edi_999_imp_filename_idx",
            ),
        ]

    def __str__(self):
        return f"{self.filename} {self.status} #{self.pk}"


class SFTPCredentialsQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related("trading_partner")


class SFTPCredentials(BaseModel):
    """
    SFTP/MFT login used to push 837P and pull acknowledgements.
    Secrets are write-only on APIs — never echo password/key material on GET.
    """

    name = models.CharField(max_length=255)
    trading_partner = models.ForeignKey(
        "trading_partner.TradingPartner",
        on_delete=models.PROTECT,
        related_name="sftp_credentials",
        null=True,
        blank=True,
    )
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.TEST,
    )
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=22)
    username = models.CharField(max_length=255)
    auth_type = models.CharField(
        max_length=32,
        choices=SFTPAuthType.choices,
        default=SFTPAuthType.PASSWORD,
    )
    password = models.CharField(max_length=255, null=True, blank=True)
    private_key_pem = models.TextField(null=True, blank=True)
    private_key_passphrase = models.CharField(max_length=255, null=True, blank=True)
    host_fingerprint = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Optional expected host key fingerprint.",
    )
    timeout_seconds = models.PositiveIntegerField(default=30)
    notes = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = SFTPCredentialsQuerySet.as_manager()

    class Meta:
        verbose_name = "SFTP Credentials"
        verbose_name_plural = "SFTP Credentials"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["name", "environment"],
                name="uniq_sftp_credentials_name_environment",
            ),
        ]
        indexes = [
            models.Index(
                fields=["environment", "is_active"],
                name="sftp_cred_env_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.environment})"


class SFTPDirectoryQuerySet(models.QuerySet):
    def with_relations(self):
        return self.select_related(
            "credentials",
            "credentials__trading_partner",
        )


class SFTPDirectory(BaseModel):
    """Remote folders for outbound claims and inbound acknowledgements."""

    credentials = models.ForeignKey(
        SFTPCredentials,
        on_delete=models.PROTECT,
        related_name="directories",
    )
    name = models.CharField(max_length=255, null=True, blank=True)
    purpose = models.CharField(
        max_length=32,
        choices=SFTPDirectoryPurpose.choices,
        default=SFTPDirectoryPurpose.GENERAL,
    )
    sending_path = models.CharField(
        max_length=500,
        help_text="Remote path for outbound uploads (837P).",
    )
    receiving_path = models.CharField(
        max_length=500,
        help_text="Remote path for inbound downloads (999/277/835).",
    )
    is_active = models.BooleanField(default=True)

    objects = SFTPDirectoryQuerySet.as_manager()

    class Meta:
        verbose_name = "SFTP Directory"
        verbose_name_plural = "SFTP Directories"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=["credentials", "purpose", "sending_path", "receiving_path"],
                condition=models.Q(is_active=True),
                name="uniq_active_sftp_directory_paths",
            ),
        ]
        indexes = [
            models.Index(
                fields=["purpose", "is_active"],
                name="sftp_dir_purpose_active_idx",
            ),
        ]

    def __str__(self):
        return self.name or f"{self.purpose} #{self.pk}"
