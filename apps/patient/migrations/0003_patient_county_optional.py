from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("patient", "0002_patient_demographics")]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="county",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
