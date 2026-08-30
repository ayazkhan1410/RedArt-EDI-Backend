from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.long_distance_rule.models import LongDistanceRule


class LongDistanceRuleCRUDTests(APITestCase):
    def setUp(self):
        self.standard, _ = LongDistanceRule.objects.update_or_create(
            county_type="STANDARD",
            defaults={
                "review_threshold": 52,
                "verification_threshold": 25,
                "is_active": True,
            },
        )

    def test_get_patch_and_soft_delete(self):
        detail_url = reverse(
            "long-distance-rule-detail", kwargs={"pk": self.standard.id}
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["data"]["review_threshold"], 52)

        patched = self.client.patch(
            detail_url, {"review_threshold": 55}, format="json"
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.standard.refresh_from_db()
        self.assertEqual(self.standard.review_threshold, 55)

        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.standard.refresh_from_db()
        self.assertFalse(self.standard.is_active)

    def test_create_rural_rule_when_missing(self):
        LongDistanceRule.objects.filter(county_type="DESIGNATED_RURAL").delete()
        url = reverse("long-distance-rule-list-create")
        response = self.client.post(
            url,
            {
                "county_type": "DESIGNATED_RURAL",
                "review_threshold": 125,
                "verification_threshold": 25,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_includes_standard(self):
        url = reverse("long-distance-rule-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 1)
        types = {row["county_type"] for row in response.data["data"]}
        self.assertIn("STANDARD", types)

    def test_invalid_threshold_rejected(self):
        url = reverse("long-distance-rule-list-create")
        LongDistanceRule.objects.filter(county_type="DESIGNATED_RURAL").delete()
        response = self.client.post(
            url,
            {
                "county_type": "DESIGNATED_RURAL",
                "review_threshold": -1,
                "verification_threshold": 25,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
