from django.db import models

from apps.core.models import BaseModel
from apps.trading_partner.choices import Environment


class TradingPartner(BaseModel):
    name = models.CharField(max_length=500, blank=True, null=True)
    sender_id = models.CharField(max_length=255, null=True, blank=True)
    receiver_id = models.CharField(max_length=255, null=True, blank=True)
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.TEST,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Trading Partner"
        verbose_name_plural = "Trading Partners"
        # UniqueConstraint already creates an index on these columns.
        constraints = [
            models.UniqueConstraint(
                fields=["sender_id", "receiver_id", "environment"],
                name="uniq_trading_partner_sender_id_receiver_id_environment",
            ),
        ]

    def __str__(self):
        return self.name or str(self.pk)
