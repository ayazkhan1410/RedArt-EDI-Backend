from django.urls import path

from apps.nemt_trip.views import (
    NemtTripDetailAPIView,
    NemtTripListCreateAPIView,
    NemtTripLongDistanceCheckAPIView,
)

urlpatterns = [
    path(
        "nemt-trips/",
        NemtTripListCreateAPIView.as_view(),
        name="nemt-trip-list-create",
    ),
    path(
        "nemt-trips/<int:pk>/",
        NemtTripDetailAPIView.as_view(),
        name="nemt-trip-detail",
    ),
    path(
        "nemt-trips/<int:pk>/long-distance-check/",
        NemtTripLongDistanceCheckAPIView.as_view(),
        name="nemt-trip-long-distance-check",
    ),
]
