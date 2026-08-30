from django.urls import path

from apps.claim.views import (
    ClaimDetailAPIView,
    ClaimFromTripAPIView,
    ClaimListCreateAPIView,
)

urlpatterns = [
    path("claims/", ClaimListCreateAPIView.as_view(), name="claim-list-create"),
    path(
        "claims/from-trip/",
        ClaimFromTripAPIView.as_view(),
        name="claim-from-trip",
    ),
    path("claims/<int:pk>/", ClaimDetailAPIView.as_view(), name="claim-detail"),
]
