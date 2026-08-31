from django.urls import reverse
from rest_framework import status
from apps.core.testing import AuthAPITestCase

from apps.provider_billing_profile.models import ProviderBillingProfile


class ProviderBillingProfileAPITests(AuthAPITestCase):
    def test_create_get_patch_and_soft_delete(self):
        list_url = reverse("provider-billing-profile-list-create")
        create = self.client.post(
            list_url,
            {
                "legal_name": "WALLA INVESTMENT LLC",
                "billing_name": "WALLA INVESTMENT LLC",
                "npi": "1750058525",
                "taxonomy_code": "343900000X",
                "location_id": "9000201481",
                "revalidation_date": "2029-11-25",
                "city": "Denver",
                "state": "co",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        profile_id = create.data["data"]["id"]

        detail_url = reverse(
            "provider-billing-profile-detail", kwargs={"pk": profile_id}
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["data"]["state"], "CO")
        self.assertEqual(detail.data["data"]["location_id"], "9000201481")

        patched = self.client.patch(
            detail_url, {"city": "Aurora"}, format="json"
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(
            ProviderBillingProfile.objects.get(pk=profile_id).city, "Aurora"
        )

        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ProviderBillingProfile.objects.get(pk=profile_id).is_active
        )

    def test_invalid_npi_rejected(self):
        url = reverse("provider-billing-profile-list-create")
        response = self.client.post(
            url, {"npi": "ABC123", "legal_name": "Bad NPI"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_npi_too_long_rejected(self):
        url = reverse("provider-billing-profile-list-create")
        response = self.client.post(
            url,
            {"npi": "12345678901", "legal_name": "Too Long"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_by_npi(self):
        ProviderBillingProfile.objects.create(
            legal_name="One", npi="1111111111"
        )
        ProviderBillingProfile.objects.create(
            legal_name="Two", npi="2222222222"
        )
        url = reverse("provider-billing-profile-list-create")
        response = self.client.get(url, {"search": "1111111111"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
