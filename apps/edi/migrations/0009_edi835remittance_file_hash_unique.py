# Unique file_hash on EDI835Remittance for idempotent imports.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edi", "0008_edi835_import"),
    ]

    operations = [
        migrations.AlterField(
            model_name="edi835remittance",
            name="file_hash",
            field=models.CharField(
                blank=True,
                help_text="SHA-256 of normalized content for idempotent re-import.",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
