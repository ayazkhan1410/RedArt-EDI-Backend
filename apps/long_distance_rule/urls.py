from django.urls import path

from apps.long_distance_rule.views import (
    LongDistanceRuleDetailAPIView,
    LongDistanceRuleListCreateAPIView,
)

urlpatterns = [
    path(
        "long-distance-rules/",
        LongDistanceRuleListCreateAPIView.as_view(),
        name="long-distance-rule-list-create",
    ),
    path(
        "long-distance-rules/<int:pk>/",
        LongDistanceRuleDetailAPIView.as_view(),
        name="long-distance-rule-detail",
    ),
]
