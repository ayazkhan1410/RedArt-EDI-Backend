# Generated manually — claim document blobs + attachment duplicate guard

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("claim", "0004_soft_delete_unique_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="claimdocument",
            name="blob_ref",
            field=models.CharField(blank=True, max_length=1024, null=True),
        ),
        migrations.AddField(
            model_name="claimdocument",
            name="content_type",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="claimdocument",
            name="file_size",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attachmentsubmission",
            name="payload_hash",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="attachmentsubmission",
            name="remote_path",
            field=models.CharField(blank=True, max_length=1024, null=True),
        ),
        migrations.AddField(
            model_name="attachmentsubmission",
            name="retry_count",
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
        migrations.AddIndex(
            model_name="attachmentsubmission",
            index=models.Index(
                fields=["claim", "payload_hash"],
                name="attach_sub_claim_payload_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="attachmentsubmission",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("is_active", True),
                    ("payload_hash__isnull", False),
                    ("status__in", ["QUEUED", "SUBMITTED", "CONFIRMED"]),
                ),
                fields=("claim", "payload_hash"),
                name="uniq_active_attachment_payload_hash",
            ),
        ),
    ]
