from django.urls import include, path

urlpatterns = [
    path("", include("apps.trading_partner.urls")),
    path("", include("apps.provider_billing_profile.urls")),
    path("", include("apps.patient.urls")),
    path("", include("apps.nemt_trip.urls")),
    path("", include("apps.long_distance_rule.urls")),
    path("", include("apps.claim.urls")),
    path("", include("apps.claim_service_line.urls")),
]
