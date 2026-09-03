"""
Migration: make Patient.date_of_birth nullable.

Per Colorado NEMT 837P billing requirements, the critical member identifier
is the Colorado Medicaid Member ID (NM1*IL MI).  Date of birth is optional
and must never be fabricated.  This migration makes the field nullable so
RedArt can create patients without DOB and the 837P generator will omit the
DMG segment rather than producing invalid EDI.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("patient", "0002_patient_demographics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="date_of_birth",
            field=models.DateField(
                blank=True,
                null=True,
                help_text=(
                    "Optional for Colorado NEMT 837P.  When present, included in "
                    "the DMG segment.  Never fabricate."
                ),
            ),
        ),
    ]
