from django.urls import reverse
from rest_framework import status
from apps.core.testing import AuthAPITestCase

from apps.trading_partner.models import TradingPartner


class TradingPartnerAPITests(AuthAPITestCase):
    def test_create_list_get_and_soft_delete(self):
        list_url = reverse("trading-partner-list-create")
        create = self.client.post(
            list_url,
            {
                "name": "Colorado Medicaid",
                "sender_id": "TP123456",
                "receiver_id": "COMEDASSISTPROG",
                "environment": "TEST",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        partner_id = create.data["data"]["id"]

        listed = self.client.get(list_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)

        detail_url = reverse("trading-partner-detail", kwargs={"pk": partner_id})
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["data"]["sender_id"], "TP123456")

        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        partner = TradingPartner.objects.get(pk=partner_id)
        self.assertFalse(partner.is_active)

    def test_hard_delete(self):
        partner = TradingPartner.objects.create(
            name="Temp",
            sender_id="TMP1",
            receiver_id="R1",
            environment="TEST",
        )
        url = reverse("trading-partner-detail", kwargs={"pk": partner.id})
        response = self.client.delete(f"{url}?hard=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(TradingPartner.objects.filter(pk=partner.id).exists())

    def test_duplicate_identifiers_rejected(self):
        url = reverse("trading-partner-list-create")
        payload = {
            "name": "Colorado Medicaid",
            "sender_id": "TP123456",
            "receiver_id": "COMEDASSISTPROG",
            "environment": "TEST",
        }
        self.assertEqual(
            self.client.post(url, payload, format="json").status_code,
            status.HTTP_201_CREATED,
        )
        dup = self.client.post(url, payload, format="json")
        self.assertIn(
            dup.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
        )

    def test_invalid_environment_filter(self):
        url = reverse("trading-partner-list-create")
        response = self.client.get(url, {"environment": "STAGING"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_page_rejected(self):
        url = reverse("trading-partner-list-create")
        response = self.client.get(url, {"page": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_by_name(self):
        TradingPartner.objects.create(
            name="Colorado Medicaid",
            sender_id="S1",
            receiver_id="R1",
            environment="TEST",
        )
        TradingPartner.objects.create(
            name="Other Payer",
            sender_id="S2",
            receiver_id="R2",
            environment="TEST",
        )
        url = reverse("trading-partner-list-create")
        response = self.client.get(url, {"search": "Colorado"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
