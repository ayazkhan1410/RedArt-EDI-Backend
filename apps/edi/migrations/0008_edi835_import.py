# Generated manually for EDI835Import SFTP poll tracking.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edi", "0007_edi835_remittance"),
    ]

    operations = [
        migrations.CreateModel(
            name="EDI835Import",
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
                ("filename", models.CharField(max_length=255)),
                ("remote_path", models.CharField(max_length=1024)),
                (
                    "file_hash",
                    models.CharField(blank=True, max_length=128, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DISCOVERED", "Discovered"),
                            ("QUEUED", "Queued"),
                            ("DOWNLOADING", "Downloading"),
                            ("PARSING", "Parsing"),
                            ("IMPORTED", "Imported"),
                            ("FAILED", "Failed"),
                            ("SKIPPED", "Skipped"),
                        ],
                        default="DISCOVERED",
                        max_length=32,
                    ),
                ),
                ("attempt", models.PositiveIntegerField(default=0)),
                (
                    "celery_task_id",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("message", models.CharField(blank=True, max_length=500, null=True)),
                ("detail", models.TextField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "credentials",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="edi_835_imports",
                        to="edi.sftpcredentials",
                    ),
                ),
                (
                    "directory",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="edi_835_imports",
                        to="edi.sftpdirectory",
                    ),
                ),
                (
                    "remittance",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="import_rows",
                        to="edi.edi835remittance",
                    ),
                ),
            ],
            options={
                "verbose_name": "EDI 835 Import",
                "verbose_name_plural": "EDI 835 Imports",
                "ordering": ("-id",),
            },
        ),
        migrations.AddIndex(
            model_name="edi835import",
            index=models.Index(
                fields=["status", "is_active"],
                name="edi_835_imp_status_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="edi835import",
            index=models.Index(fields=["file_hash"], name="edi_835_imp_hash_idx"),
        ),
        migrations.AddIndex(
            model_name="edi835import",
            index=models.Index(fields=["filename"], name="edi_835_imp_filename_idx"),
        ),
        migrations.AddConstraint(
            model_name="edi835import",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("credentials__isnull", False),
                    ("remote_path__isnull", False),
                    ("is_active", True),
                ),
                fields=("credentials", "remote_path"),
                name="uniq_active_edi_835_import_remote_path",
            ),
        ),
    ]
