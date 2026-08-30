from django.db import migrations


def seed_default_rules(apps, schema_editor):
    LongDistanceRule = apps.get_model("long_distance_rule", "LongDistanceRule")
    defaults = [
        {
            "county_type": "STANDARD",
            "review_threshold": 52,
            "verification_threshold": 25,
            "is_active": True,
        },
        {
            "county_type": "DESIGNATED_RURAL",
            "review_threshold": 125,
            "verification_threshold": 25,
            "is_active": True,
        },
    ]
    for row in defaults:
        LongDistanceRule.objects.update_or_create(
            county_type=row["county_type"],
            defaults={
                "review_threshold": row["review_threshold"],
                "verification_threshold": row["verification_threshold"],
                "is_active": row["is_active"],
            },
        )


def unseed_default_rules(apps, schema_editor):
    LongDistanceRule = apps.get_model("long_distance_rule", "LongDistanceRule")
    LongDistanceRule.objects.filter(
        county_type__in=["STANDARD", "DESIGNATED_RURAL"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("long_distance_rule", "0001_initial_long_distance_rule"),
    ]

    operations = [
        migrations.RunPython(seed_default_rules, unseed_default_rules),
    ]
