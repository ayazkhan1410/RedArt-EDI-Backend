from django.urls import reverse
from rest_framework import status
from apps.core.testing import AuthAPITestCase

from apps.edi.models import SFTPCredentials, SFTPDirectory
from apps.trading_partner.models import TradingPartner


class SFTPAPITests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.partner = TradingPartner.objects.create(
            name="Colorado Medicaid",
            sender_id="TP-SFTP",
            receiver_id="COMEDASSISTPROG",
            environment="TEST",
        )

    def test_create_credentials_hides_password_on_get(self):
        url = reverse("sftp-credentials-list-create")
        created = self.client.post(
            url,
            {
                "name": "CO TEST MFT",
                "trading_partner": self.partner.id,
                "environment": "TEST",
                "host": "mft-test.example.com",
                "port": 22,
                "username": "redart_test",
                "auth_type": "PASSWORD",
                "password": "super-secret",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        cred_id = created.data["data"]["id"]

        detail = self.client.get(
            reverse("sftp-credentials-detail", kwargs={"pk": cred_id})
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        body = detail.data["data"]
        self.assertNotIn("password", body)
        self.assertTrue(body["has_password"])
        self.assertFalse(body["has_private_key"])
        stored = SFTPCredentials.objects.get(pk=cred_id).password
        self.assertTrue(str(stored).startswith("fernet:"))
        from apps.core.crypto_secrets import decrypt_secret

        self.assertEqual(decrypt_secret(stored), "super-secret")

    def test_password_required_for_password_auth(self):
        response = self.client.post(
            reverse("sftp-credentials-list-create"),
            {
                "name": "Missing password",
                "host": "mft.example.com",
                "username": "u1",
                "auth_type": "PASSWORD",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_port_rejected(self):
        response = self.client.post(
            reverse("sftp-credentials-list-create"),
            {
                "name": "Bad port",
                "host": "mft.example.com",
                "username": "u1",
                "auth_type": "PASSWORD",
                "password": "x",
                "port": 70000,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_without_password_keeps_existing_secret(self):
        cred = SFTPCredentials.objects.create(
            name="Keep secret",
            host="mft.example.com",
            username="u1",
            auth_type="PASSWORD",
            password="keep-me",
            environment="TEST",
        )
        response = self.client.patch(
            reverse("sftp-credentials-detail", kwargs={"pk": cred.id}),
            {"host": "mft2.example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cred.refresh_from_db()
        self.assertEqual(cred.host, "mft2.example.com")
        self.assertEqual(cred.password, "keep-me")

    def test_directory_crud_and_path_validation(self):
        cred = SFTPCredentials.objects.create(
            name="Dirs",
            host="mft.example.com",
            username="u1",
            auth_type="PASSWORD",
            password="x",
            environment="TEST",
        )
        bad = self.client.post(
            reverse("sftp-directory-list-create"),
            {
                "credentials": cred.id,
                "purpose": "OUTBOUND_837P",
                "sending_path": "/out/../secret",
                "receiving_path": "/in",
            },
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        created = self.client.post(
            reverse("sftp-directory-list-create"),
            {
                "credentials": cred.id,
                "name": "837 outbound",
                "purpose": "OUTBOUND_837P",
                "sending_path": "/outbound/837p",
                "receiving_path": "/inbound/999",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        dir_id = created.data["data"]["id"]

        listed = self.client.get(
            reverse("sftp-directory-list-create"),
            {"credentials_id": cred.id},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)

        soft = self.client.delete(
            reverse("sftp-directory-detail", kwargs={"pk": dir_id})
        )
        self.assertEqual(soft.status_code, status.HTTP_200_OK)
        self.assertFalse(SFTPDirectory.objects.get(pk=dir_id).is_active)

    def test_hard_delete_credentials_blocked_with_active_directory(self):
        cred = SFTPCredentials.objects.create(
            name="Protected",
            host="mft.example.com",
            username="u1",
            auth_type="PASSWORD",
            password="x",
            environment="TEST",
        )
        SFTPDirectory.objects.create(
            credentials=cred,
            purpose="GENERAL",
            sending_path="/out",
            receiving_path="/in",
        )
        response = self.client.delete(
            f"{reverse('sftp-credentials-detail', kwargs={'pk': cred.id})}?hard=true"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(SFTPCredentials.objects.filter(pk=cred.id).exists())

    def test_duplicate_name_environment_rejected(self):
        payload = {
            "name": "Dup",
            "host": "mft.example.com",
            "username": "u1",
            "auth_type": "PASSWORD",
            "password": "x",
            "environment": "TEST",
        }
        url = reverse("sftp-credentials-list-create")
        self.assertEqual(
            self.client.post(url, payload, format="json").status_code,
            status.HTTP_201_CREATED,
        )
        dup = self.client.post(url, payload, format="json")
        self.assertIn(
            dup.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
        )

    def test_inactive_credentials_rejected_for_directory(self):
        cred = SFTPCredentials.objects.create(
            name="Inactive",
            host="mft.example.com",
            username="u1",
            auth_type="PASSWORD",
            password="x",
            environment="TEST",
            is_active=False,
        )
        response = self.client.post(
            reverse("sftp-directory-list-create"),
            {
                "credentials": cred.id,
                "sending_path": "/out",
                "receiving_path": "/in",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
