from django.urls import path

from apps.provider_billing_profile.views import (
    ProviderBillingProfileDetailAPIView,
    ProviderBillingProfileListCreateAPIView,
)

urlpatterns = [
    path(
        "provider-billing-profiles/",
        ProviderBillingProfileListCreateAPIView.as_view(),
        name="provider-billing-profile-list-create",
    ),
    path(
        "provider-billing-profiles/<int:pk>/",
        ProviderBillingProfileDetailAPIView.as_view(),
        name="provider-billing-profile-detail",
    ),
]
