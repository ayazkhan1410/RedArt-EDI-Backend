"""Integration discovery URLs (Lovable / RedArt)."""

from django.urls import path

from apps.core.integration_views import LovableIntegrationCatalogAPIView

urlpatterns = [
    path(
        "integration/lovable/",
        LovableIntegrationCatalogAPIView.as_view(),
        name="integration-lovable-catalog",
    ),
]
