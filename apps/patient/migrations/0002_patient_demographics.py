# Patient demographics for 837P subscriber loops

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("patient", "0001_initial_patient"),
    ]

    operations = [
        migrations.AddField(
            model_name="patient",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("M", "Male"), ("F", "Female"), ("U", "Unknown")],
                max_length=1,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="patient",
            name="address_line_1",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="patient",
            name="address_line_2",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="patient",
            name="city",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="patient",
            name="state",
            field=models.CharField(blank=True, max_length=2, null=True),
        ),
        migrations.AddField(
            model_name="patient",
            name="zip",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="patient",
            name="phone",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
