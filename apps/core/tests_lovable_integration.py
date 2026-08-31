"""Lovable integration catalog + helper unit tests."""

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.lovable_helpers import (
    AUTH_TOKEN_PATH,
    absolute_url,
    bearer_headers,
    build_lovable_catalog,
    fill_path,
)


class LovableHelperTests(SimpleTestCase):
    def test_bearer_headers(self):
        headers = bearer_headers("abc.token")
        self.assertEqual(headers["Authorization"], "Bearer abc.token")
        self.assertEqual(bearer_headers("Bearer xyz")["Authorization"], "Bearer xyz")

    def test_fill_path(self):
        self.assertEqual(fill_path("/api/v1/claims/{id}/status/", id=42), "/api/v1/claims/42/status/")

    @override_settings(EDI_PUBLIC_BASE_URL="https://edi.example.com")
    def test_catalog_uses_public_base(self):
        catalog = build_lovable_catalog()
        self.assertEqual(catalog["base_url"], "https://edi.example.com")
        self.assertIn(AUTH_TOKEN_PATH, catalog["auth"]["token_url"])
        self.assertTrue(catalog["happy_path"])


class LovableCatalogAPITests(APITestCase):
    def test_catalog_endpoint_public(self):
        response = self.client.get(reverse("integration-lovable-catalog"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("auth", data)
        self.assertIn("happy_path", data)
        self.assertIn("env_secrets", data)
        self.assertTrue(absolute_url("/api/docs/").endswith("/api/docs/"))
