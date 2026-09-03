from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edi", "0011_edi277_import"),
    ]

    operations = [
        migrations.AddField(
            model_name="edifile",
            name="content",
            field=models.TextField(blank=True, null=True),
        ),
    ]
