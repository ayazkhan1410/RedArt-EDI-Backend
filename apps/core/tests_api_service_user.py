"""Tests for API service user + JWT authorization rules."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.auth_constants import API_SERVICE_GROUP_NAME

User = get_user_model()


class CreateApiServiceUserCommandTests(TestCase):
    def test_create_generate_password_and_group(self):
        call_command(
            "create_api_service_user",
            username="redart_api",
            generate_password=True,
        )
        user = User.objects.get(username="redart_api")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.groups.filter(name=API_SERVICE_GROUP_NAME).exists())

    def test_existing_user_requires_rotate(self):
        call_command(
            "create_api_service_user",
            username="redart_api",
            generate_password=True,
        )
        with self.assertRaises(CommandError):
            call_command(
                "create_api_service_user",
                username="redart_api",
                password="AnotherPass123!@#",
            )

    def test_rotate_password(self):
        call_command(
            "create_api_service_user",
            username="redart_api",
            generate_password=True,
        )
        call_command(
            "create_api_service_user",
            username="redart_api",
            password="RotatedPass123!@#x",
            rotate_password=True,
        )
        user = User.objects.get(username="redart_api")
        self.assertTrue(user.check_password("RotatedPass123!@#x"))


class ServiceTokenAuthTests(APITestCase):
    def setUp(self):
        self.password = "ServicePass123!@#xx"
        self.service = User.objects.create_user(
            username="svc_redart",
            password=self.password,
            email="svc@edi.local",
        )
        self.service.is_staff = False
        self.service.is_superuser = False
        self.service.save()
        group, _ = Group.objects.get_or_create(name=API_SERVICE_GROUP_NAME)
        self.service.groups.add(group)

        self.plain = User.objects.create_user(
            username="plain_user",
            password=self.password,
        )

    def test_service_user_obtains_token(self):
        response = self.client.post(
            reverse("auth-token-obtain"),
            {"username": "svc_redart", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data.get("token_type"), "Bearer")
        self.assertIn("expires_in", response.data)

    def test_plain_user_denied(self):
        response = self.client.post(
            reverse("auth-token-obtain"),
            {"username": "plain_user", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bad_password_denied(self):
        response = self.client.post(
            reverse("auth-token-obtain"),
            {"username": "svc_redart", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_service_denied(self):
        self.service.is_active = False
        self.service.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("auth-token-obtain"),
            {"username": "svc_redart", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_misconfigured_service_staff_denied(self):
        self.service.is_staff = True
        self.service.save(update_fields=["is_staff"])
        response = self.client.post(
            reverse("auth-token-obtain"),
            {"username": "svc_redart", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
