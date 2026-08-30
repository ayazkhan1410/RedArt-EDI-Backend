from django.db import models


class TransactionType(models.TextChoices):
    X837P = "837P", "837 Professional"
    X999 = "999", "Implementation Acknowledgment"
    X277 = "277", "Claim Status"
    OTHER = "OTHER", "Other"


class EDIFileStatus(models.TextChoices):
    GENERATED = "GENERATED", "Generated"
    UPLOADED = "UPLOADED", "Uploaded"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    FAILED = "FAILED", "Failed"
    ARCHIVED = "ARCHIVED", "Archived"


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
