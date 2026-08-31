from django.db import models


class TransactionType(models.TextChoices):
    X837P = "837P", "837 Professional"
    X999 = "999", "Implementation Acknowledgment"
    X277 = "277", "Claim Status"
    OTHER = "OTHER", "Other"


class AcknowledgementType(models.TextChoices):
    X999 = "999", "Implementation Acknowledgment"
    X277 = "277", "Claim Status"
    OTHER = "OTHER", "Other"


class AcknowledgementStatus(models.TextChoices):
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    PARTIAL = "PARTIAL", "Partial"
    ERROR = "ERROR", "Error"


class EDIFileStatus(models.TextChoices):
    GENERATED = "GENERATED", "Generated"
    UPLOAD_QUEUED = "UPLOAD_QUEUED", "Upload queued"
    UPLOADED = "UPLOADED", "Uploaded"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    FAILED = "FAILED", "Failed"
    ARCHIVED = "ARCHIVED", "Archived"


class TransferChannel(models.TextChoices):
    SFTP = "SFTP", "SFTP"
    S3 = "S3", "S3 / MinIO"


class TransferLogStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"


class EDI999ImportStatus(models.TextChoices):
    DISCOVERED = "DISCOVERED", "Discovered"
    QUEUED = "QUEUED", "Queued"
    DOWNLOADING = "DOWNLOADING", "Downloading"
    PARSING = "PARSING", "Parsing"
    IMPORTED = "IMPORTED", "Imported"
    FAILED = "FAILED", "Failed"
    SKIPPED = "SKIPPED", "Skipped"


class SFTPAuthType(models.TextChoices):
    PASSWORD = "PASSWORD", "Password"
    PRIVATE_KEY = "PRIVATE_KEY", "Private key"
    PASSWORD_AND_KEY = "PASSWORD_AND_KEY", "Password and private key"


class SFTPDirectoryPurpose(models.TextChoices):
    OUTBOUND_837P = "OUTBOUND_837P", "Outbound 837P"
    INBOUND_999 = "INBOUND_999", "Inbound 999"
    INBOUND_277 = "INBOUND_277", "Inbound 277"
    INBOUND_835 = "INBOUND_835", "Inbound 835"
    GENERAL = "GENERAL", "General send/receive"
