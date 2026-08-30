from django.db import models

from apps.core.models import BaseModel
from apps.long_distance_rule.choices import CountyType


class LongDistanceRule(BaseModel):
    county_type = models.CharField(
        max_length=32,
        choices=CountyType.choices,
        null=True,
        blank=True,
    )
    review_threshold = models.PositiveIntegerField(null=True, blank=True)
    verification_threshold = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Long Distance Rule"
        verbose_name_plural = "Long Distance Rules"
        constraints = [
            models.UniqueConstraint(
                fields=["county_type"],
                name="uniq_long_distance_rule_county_type",
            ),
        ]

    def __str__(self):
        return f"{self.county_type or 'UNSET'} ({self.review_threshold}/{self.verification_threshold})"
