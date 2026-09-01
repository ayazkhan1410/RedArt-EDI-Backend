from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("claim", "0005_document_blob_and_attachment_guard"),
    ]

    operations = [
        migrations.AddField(
            model_name="claimdocument",
            name="service_date",
            field=models.DateField(
                blank=True,
                help_text="Trip/service date shown on the standard trip log.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="claimdocument",
            name="verification_date",
            field=models.DateField(
                blank=True,
                help_text="Verification date on the 25+ mile verification form.",
                null=True,
            ),
        ),
    ]
