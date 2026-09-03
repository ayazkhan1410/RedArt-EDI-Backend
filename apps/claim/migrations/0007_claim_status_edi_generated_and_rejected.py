"""
Migration: add EDI_GENERATED and EDI_REJECTED to ClaimStatus TextChoices.

These are no-op at the database level (Django CharField choices are not DB
CHECK constraints).  The migration records the choices change in the migration
history so the state is consistent.

EDI_GENERATED — 837P file has been generated (not yet uploaded).
EDI_REJECTED  — 999/TA1 received and rejected; claim needs correction.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("claim", "0006_claimdocument_service_and_verification_dates"),
    ]

    operations = [
        migrations.AlterField(
            model_name="claim",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("DRAFT", "Draft"),
                    ("DOCUMENTS_REQUIRED", "Documents required"),
                    ("DOCUMENTS_COMPLETE", "Documents complete"),
                    ("READY_FOR_837P", "Ready for 837P"),
                    ("EDI_GENERATED", "837P generated (pending upload)"),
                    ("EDI_SENT", "837P sent/uploaded"),
                    ("EDI_ACCEPTED", "999/TA1 accepted"),
                    ("EDI_REJECTED", "999/TA1 rejected"),
                    ("ATTACHMENT_REQUIRED", "Attachment required"),
                    ("ATTACHMENT_QUEUED", "Attachment queued"),
                    ("ATTACHMENT_SUBMITTED", "Attachment submitted"),
                    ("ATTACHMENT_CONFIRMED", "Attachment confirmed"),
                    ("UNDER_REVIEW", "Under review / adjudicating"),
                    ("PAID", "Paid"),
                    ("DENIED", "Denied"),
                ],
                default="DRAFT",
                max_length=32,
                null=True,
            ),
        ),
    ]
