"""JWT serializers with service-account authorization checks."""

from __future__ import annotations

from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings

from apps.core.auth_constants import API_SERVICE_GROUP_NAME


class ServiceTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Issue tokens only to active API service accounts (group) or staff/superuser.
    Generic errors reduce username enumeration.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if not user.is_active:
            raise AuthenticationFailed(
                "No active account found with the given credentials.",
                code="no_active_account",
            )

        is_service = user.groups.filter(name=API_SERVICE_GROUP_NAME).exists()
        if is_service and (user.is_staff or user.is_superuser):
            # Misconfigured service account — refuse rather than elevate.
            raise AuthenticationFailed(
                "No active account found with the given credentials.",
                code="no_active_account",
            )
        if not (is_service or user.is_staff or user.is_superuser):
            raise AuthenticationFailed(
                "No active account found with the given credentials.",
                code="no_active_account",
            )

        refresh = self.get_token(user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["token_type"] = "Bearer"
        data["expires_in"] = int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds())
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.get_username()
        token["svc"] = bool(user.groups.filter(name=API_SERVICE_GROUP_NAME).exists())
        return token
