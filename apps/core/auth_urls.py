"""JWT auth endpoints for RedArt server-to-server integration."""

from django.urls import path
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

TAG = "auth"


@extend_schema_view(
    post=extend_schema(
        tags=[TAG],
        summary="Obtain JWT access + refresh tokens",
        description=(
            "RedArt backend exchanges service-user credentials for a Bearer token. "
            "Send `Authorization: Bearer <access>` on subsequent /api/v1/ calls."
        ),
    )
)
class AuthTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]


@extend_schema_view(
    post=extend_schema(tags=[TAG], summary="Refresh JWT access token")
)
class AuthTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]


@extend_schema_view(
    post=extend_schema(tags=[TAG], summary="Verify JWT access token")
)
class AuthTokenVerifyView(TokenVerifyView):
    permission_classes = [AllowAny]


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
