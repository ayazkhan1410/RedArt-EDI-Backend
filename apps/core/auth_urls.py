"""JWT auth endpoints for RedArt server-to-server integration."""

from django.urls import path
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from apps.core.auth_serializers import ServiceTokenObtainPairSerializer

TAG = "auth"


class AuthBurstThrottle(AnonRateThrottle):
    """Limit credential stuffing / token grinding from anonymous clients."""

    scope = "auth_burst"


class AuthTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstThrottle]
    serializer_class = ServiceTokenObtainPairSerializer


class AuthTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstThrottle]


class AuthTokenVerifyView(TokenVerifyView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstThrottle]


AuthTokenObtainPairView = extend_schema_view(
    post=extend_schema(
        tags=[TAG],
        summary="Obtain JWT access + refresh tokens",
        description=(
            "RedArt backend exchanges **API service user** credentials for a Bearer token. "
            "Create the user with: `python manage.py create_api_service_user --generate-password`. "
            "Send `Authorization: Bearer <access>` on subsequent /api/v1/ calls. "
            "Rate-limited to reduce brute-force risk."
        ),
    )
)(AuthTokenObtainPairView)

AuthTokenRefreshView = extend_schema_view(
    post=extend_schema(tags=[TAG], summary="Refresh JWT access token")
)(AuthTokenRefreshView)

AuthTokenVerifyView = extend_schema_view(
    post=extend_schema(tags=[TAG], summary="Verify JWT access token")
)(AuthTokenVerifyView)


urlpatterns = [
    path("auth/token/", AuthTokenObtainPairView.as_view(), name="auth-token-obtain"),
    path(
        "auth/token/refresh/",
        AuthTokenRefreshView.as_view(),
        name="auth-token-refresh",
    ),
    path(
        "auth/token/verify/",
        AuthTokenVerifyView.as_view(),
        name="auth-token-verify",
    ),
]
