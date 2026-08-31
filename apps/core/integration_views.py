"""Public integration catalog for Lovable / RedArt clients."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.lovable_helpers import build_lovable_catalog
from apps.core.utils.responses import success_response


class IntegrationBurstThrottle(AnonRateThrottle):
    scope = "auth_burst"


class LovableIntegrationCatalogAPIView(APIView):
    """
    Picture-perfect endpoint map for Lovable.
    No secrets — safe to AllowAny + rate-limited.
    """

    permission_classes = [AllowAny]
    throttle_classes = [IntegrationBurstThrottle]
    authentication_classes = []

    @extend_schema(
        tags=["integration"],
        summary="Lovable / RedArt integration catalog",
        description=(
            "Returns base URL, auth steps, env secrets names, happy-path order, "
            "and key endpoint templates. Use this when wiring Lovable to the EDI API."
        ),
    )
    def get(self, request):
        return success_response(
            "Lovable integration catalog.",
            data=build_lovable_catalog(),
        )
