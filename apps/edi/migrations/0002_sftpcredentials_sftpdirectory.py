# SFTPCredentials + SFTPDirectory

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edi", "0001_initial"),
        ("trading_partner", "0003_remove_extra_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="SFTPCredentials",
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
                ("name", models.CharField(max_length=255)),
                (
                    "environment",
                    models.CharField(
                        choices=[("TEST", "Test"), ("PRODUCTION", "Production")],
                        default="TEST",
                        max_length=20,
                    ),
                ),
                ("host", models.CharField(max_length=255)),
                ("port", models.PositiveIntegerField(default=22)),
                ("username", models.CharField(max_length=255)),
                (
                    "auth_type",
                    models.CharField(
                        choices=[
                            ("PASSWORD", "Password"),
                            ("PRIVATE_KEY", "Private key"),
                            ("PASSWORD_AND_KEY", "Password and private key"),
                        ],
                        default="PASSWORD",
                        max_length=32,
                    ),
                ),
                ("password", models.CharField(blank=True, max_length=255, null=True)),
                ("private_key_pem", models.TextField(blank=True, null=True)),
                (
                    "private_key_passphrase",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "host_fingerprint",
                    models.CharField(
                        blank=True,
                        help_text="Optional expected host key fingerprint.",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("timeout_seconds", models.PositiveIntegerField(default=30)),
                ("notes", models.CharField(blank=True, max_length=500, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "trading_partner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sftp_credentials",
                        to="trading_partner.tradingpartner",
                    ),
                ),
            ],
            options={
                "verbose_name": "SFTP Credentials",
                "verbose_name_plural": "SFTP Credentials",
                "ordering": ("-id",),
            },
        ),
        migrations.CreateModel(
            name="SFTPDirectory",
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
                ("name", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("OUTBOUND_837P", "Outbound 837P"),
                            ("INBOUND_999", "Inbound 999"),
                            ("INBOUND_277", "Inbound 277"),
                            ("INBOUND_835", "Inbound 835"),
                            ("GENERAL", "General send/receive"),
                        ],
                        default="GENERAL",
                        max_length=32,
                    ),
                ),
                (
                    "sending_path",
                    models.CharField(
                        help_text="Remote path for outbound uploads (837P).",
                        max_length=500,
                    ),
                ),
                (
                    "receiving_path",
                    models.CharField(
                        help_text="Remote path for inbound downloads (999/277/835).",
                        max_length=500,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "credentials",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="directories",
                        to="edi.sftpcredentials",
                    ),
                ),
            ],
            options={
                "verbose_name": "SFTP Directory",
                "verbose_name_plural": "SFTP Directories",
                "ordering": ("-id",),
            },
        ),
        migrations.AddConstraint(
            model_name="sftpcredentials",
            constraint=models.UniqueConstraint(
                fields=("name", "environment"),
                name="uniq_sftp_credentials_name_environment",
            ),
        ),
        migrations.AddIndex(
            model_name="sftpcredentials",
            index=models.Index(
                fields=["environment", "is_active"],
                name="sftp_cred_env_active_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="sftpdirectory",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("credentials", "purpose", "sending_path", "receiving_path"),
                name="uniq_active_sftp_directory_paths",
            ),
        ),
        migrations.AddIndex(
            model_name="sftpdirectory",
            index=models.Index(
                fields=["purpose", "is_active"],
                name="sftp_dir_purpose_active_idx",
            ),
        ),
    ]
