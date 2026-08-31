"""Rural county seed + 125-mile threshold tests."""

from django.test import TestCase, override_settings

from apps.long_distance_rule.models import LongDistanceRule
from apps.long_distance_rule.utils.counties import (
    DESIGNATED_RURAL_COUNTIES,
    resolve_county_type,
)
from apps.long_distance_rule.utils.service import evaluate_trip_mileage


class RuralCountySeedTests(TestCase):
    def setUp(self):
        LongDistanceRule.objects.update_or_create(
            county_type="STANDARD",
            defaults={
                "review_threshold": 52,
                "verification_threshold": 25,
                "is_active": True,
            },
        )
        LongDistanceRule.objects.update_or_create(
            county_type="DESIGNATED_RURAL",
            defaults={
                "review_threshold": 125,
                "verification_threshold": 25,
                "is_active": True,
            },
        )

    def test_hcpf_rural_list_seeded(self):
        self.assertIn("Alamosa", DESIGNATED_RURAL_COUNTIES)
        self.assertIn("Sedgwick", DESIGNATED_RURAL_COUNTIES)
        self.assertGreaterEqual(len(DESIGNATED_RURAL_COUNTIES), 40)

    def test_resolve_rural_case_insensitive(self):
        self.assertEqual(resolve_county_type("alamosa"), "DESIGNATED_RURAL")
        self.assertEqual(resolve_county_type("Denver"), "STANDARD")

    @override_settings(EDI_RURAL_COUNTIES="FakeRural, Other")
    def test_env_override(self):
        self.assertEqual(resolve_county_type("FakeRural"), "DESIGNATED_RURAL")
        self.assertEqual(resolve_county_type("Alamosa"), "STANDARD")

    def test_evaluate_uses_125_for_rural(self):
        result = evaluate_trip_mileage(
            one_way_miles=80,
            mileage_units=80,
            county="Gunnison",
        )
        self.assertEqual(result["county_type"], "DESIGNATED_RURAL")
        self.assertEqual(int(result["review_threshold"]), 125)
        self.assertFalse(result["attachment_required"])

        result_over = evaluate_trip_mileage(
            one_way_miles=130,
            mileage_units=130,
            county="Gunnison",
        )
        self.assertTrue(result_over["attachment_required"])
