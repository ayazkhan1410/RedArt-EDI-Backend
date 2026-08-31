from django.db import models


class ClaimStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    DOCUMENTS_REQUIRED = "DOCUMENTS_REQUIRED", "Documents required"
    DOCUMENTS_COMPLETE = "DOCUMENTS_COMPLETE", "Documents complete"
    READY_FOR_837P = "READY_FOR_837P", "Ready for 837P"
    EDI_SENT = "EDI_SENT", "837P sent"
    EDI_ACCEPTED = "EDI_ACCEPTED", "EDI accepted"
    ATTACHMENT_REQUIRED = "ATTACHMENT_REQUIRED", "Attachment required"
    ATTACHMENT_QUEUED = "ATTACHMENT_QUEUED", "Attachment queued"
    ATTACHMENT_SUBMITTED = "ATTACHMENT_SUBMITTED", "Attachment submitted"
    ATTACHMENT_CONFIRMED = "ATTACHMENT_CONFIRMED", "Attachment confirmed"
    UNDER_REVIEW = "UNDER_REVIEW", "Under review"
    PAID = "PAID", "Paid"
    DENIED = "DENIED", "Denied"


class AttachmentRoute(models.TextChoices):
    HCPF_APPROVED_CHANNEL = "HCPF_APPROVED_CHANNEL", "HCPF approved channel"
    HCPF_PORTAL = "HCPF_PORTAL", "HCPF provider portal"
    NONE = "NONE", "None"


class AttachmentStatus(models.TextChoices):
    NOT_REQUIRED = "NOT_REQUIRED", "Not required"
    PENDING = "PENDING", "Pending"
    QUEUED = "QUEUED", "Queued"
    SUBMITTED = "SUBMITTED", "Submitted"
    CONFIRMED = "CONFIRMED", "Confirmed"
    FAILED = "FAILED", "Failed"


class AttachmentSubmissionStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SUBMITTED = "SUBMITTED", "Submitted"
    CONFIRMED = "CONFIRMED", "Confirmed"
    FAILED = "FAILED", "Failed"


class DocumentType(models.TextChoices):
    STANDARD_TRIP_LOG = "STANDARD_TRIP_LOG", "Standard trip log"
    MILE_25_VERIFICATION = "MILE_25_VERIFICATION", "25+ mile verification"
    OTHER = "OTHER", "Other"


class DocumentStatus(models.TextChoices):
    MISSING = "MISSING", "Missing"
    PENDING = "PENDING", "Pending"
    COMPLETE = "COMPLETE", "Complete"


class BatchStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    READY = "READY", "Ready"
    GENERATED = "GENERATED", "837P generated"
    SUBMITTED = "SUBMITTED", "Submitted"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    FAILED = "FAILED", "Failed"
