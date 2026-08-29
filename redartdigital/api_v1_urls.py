from django.urls import include, path

urlpatterns = [
    path("", include("apps.trading_partner.urls")),
    path("", include("apps.provider_billing_profile.urls")),
]
