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
