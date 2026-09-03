from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("patient", "0003_patient_county_optional"),
        ("patient", "0003_patient_dob_nullable"),
    ]

    operations = []
