from rest_framework import serializers

from apps.trading_partner.choices import Environment
from apps.trading_partner.models import TradingPartner


class TradingPartnerSerializer(serializers.ModelSerializer):
    environment = serializers.ChoiceField(choices=Environment.choices)

    class Meta:
        model = TradingPartner
        fields = (
            "id",
            "name",
            "sender_id",
            "receiver_id",
            "contact_name",
            "contact_phone",
            "environment",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_sender_id(self, value):
        if value is None:
            return value
        value = value.strip()
        return value or None

    def validate_receiver_id(self, value):
        if value is None:
            return value
        value = value.strip()
        return value or None

    def validate_name(self, value):
        if value is None:
            return value
        value = value.strip()
        return value or None

    def validate(self, attrs):
        sender_id = attrs.get("sender_id", getattr(self.instance, "sender_id", None))
        receiver_id = attrs.get(
            "receiver_id", getattr(self.instance, "receiver_id", None)
        )
        environment = attrs.get(
            "environment", getattr(self.instance, "environment", None)
        )

        if sender_id and receiver_id and environment:
            qs = TradingPartner.objects.filter(
                sender_id=sender_id,
                receiver_id=receiver_id,
                environment=environment,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "A trading partner with this sender_id, "
                            "receiver_id, and environment already exists."
                        ]
                    }
                )
        return attrs


class TradingPartnerListSerializer(serializers.ModelSerializer):
    """Lighter payload for list endpoints."""

    class Meta:
        model = TradingPartner
        fields = (
            "id",
            "name",
            "sender_id",
            "receiver_id",
            "environment",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class TradingPartnerIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
