# Generated manually for EDIFileTransferLog + UPLOAD_QUEUED status support

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edi", "0002_sftpcredentials_sftpdirectory"),
    ]

    operations = [
        migrations.AlterField(
            model_name="edifile",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("GENERATED", "Generated"),
                    ("UPLOAD_QUEUED", "Upload queued"),
                    ("UPLOADED", "Uploaded"),
                    ("ACKNOWLEDGED", "Acknowledged"),
                    ("FAILED", "Failed"),
                    ("ARCHIVED", "Archived"),
                ],
                default="GENERATED",
                max_length=32,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="EDIFileTransferLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "channel",
                    models.CharField(
                        choices=[("SFTP", "SFTP"), ("S3", "S3 / MinIO")],
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("IN_PROGRESS", "In progress"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=32,
                    ),
                ),
                ("attempt", models.PositiveIntegerField(default=1)),
                (
                    "remote_path",
                    models.CharField(blank=True, max_length=1024, null=True),
                ),
                ("message", models.CharField(blank=True, max_length=500, null=True)),
                ("detail", models.TextField(blank=True, null=True)),
                (
                    "celery_task_id",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "edi_file",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transfer_logs",
                        to="edi.edifile",
                    ),
                ),
            ],
            options={
                "verbose_name": "EDI File Transfer Log",
                "verbose_name_plural": "EDI File Transfer Logs",
                "ordering": ("-id",),
            },
        ),
        migrations.AddIndex(
            model_name="edifiletransferlog",
            index=models.Index(
                fields=["edi_file", "channel"],
                name="edi_xfer_file_channel_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="edifiletransferlog",
            index=models.Index(
                fields=["status", "is_active"],
                name="edi_xfer_status_active_idx",
            ),
        ),
    ]
