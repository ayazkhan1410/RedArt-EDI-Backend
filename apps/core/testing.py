"""Shared DRF test base that authenticates a staff service-style user."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.auth_constants import API_SERVICE_GROUP_NAME

User = get_user_model()


class AuthAPITestCase(APITestCase):
    """
    Authenticate every request so Docker IsAuthenticated default works.

    Subclasses that override setUp MUST call super().setUp().
    Set authenticate_by_default = False for token/anonymous suites.
    """

    authenticate_by_default = True

    def setUp(self):
        super().setUp()
        if not self.authenticate_by_default:
            return
        self.auth_user = User.objects.create_user(
            username=f"api_tester_{self._testMethodName}"[:30],
            password="TestPass123!@#xx",
            email="tester@edi.local",
        )
        self.auth_user.is_staff = True
        self.auth_user.save(update_fields=["is_staff"])
        group, _ = Group.objects.get_or_create(name=API_SERVICE_GROUP_NAME)
        self.auth_user.groups.add(group)
        self.client.force_authenticate(user=self.auth_user)
