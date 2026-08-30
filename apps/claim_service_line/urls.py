from django.urls import path

from apps.claim_service_line.views import (
    ClaimServiceLineDetailAPIView,
    ClaimServiceLineListCreateAPIView,
)

urlpatterns = [
    path(
        "claim-service-lines/",
        ClaimServiceLineListCreateAPIView.as_view(),
        name="claim-service-line-list-create",
    ),
    path(
        "claim-service-lines/<int:pk>/",
        ClaimServiceLineDetailAPIView.as_view(),
        name="claim-service-line-detail",
    ),
]
