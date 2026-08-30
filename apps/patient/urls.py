from django.urls import path

from apps.patient.views import PatientDetailAPIView, PatientListCreateAPIView

urlpatterns = [
    path(
        "patients/",
        PatientListCreateAPIView.as_view(),
        name="patient-list-create",
    ),
    path(
        "patients/<int:pk>/",
        PatientDetailAPIView.as_view(),
        name="patient-detail",
    ),
]
