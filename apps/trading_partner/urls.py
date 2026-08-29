from django.urls import path

from apps.trading_partner.views import (
    TradingPartnerDetailAPIView,
    TradingPartnerListCreateAPIView,
)

urlpatterns = [
    path(
        "trading-partners/",
        TradingPartnerListCreateAPIView.as_view(),
        name="trading-partner-list-create",
    ),
    path(
        "trading-partners/<int:pk>/",
        TradingPartnerDetailAPIView.as_view(),
        name="trading-partner-detail",
    ),
]
