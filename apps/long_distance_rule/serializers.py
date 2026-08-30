from rest_framework import serializers

from apps.long_distance_rule.choices import CountyType
from apps.long_distance_rule.models import LongDistanceRule


class LongDistanceRuleSerializer(serializers.ModelSerializer):
    county_type = serializers.ChoiceField(
        choices=CountyType.choices,
        required=True,
    )

    class Meta:
        model = LongDistanceRule
        fields = (
            "id",
            "county_type",
            "review_threshold",
            "verification_threshold",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_review_threshold(self, value):
        if value is None:
            raise serializers.ValidationError("review_threshold is required.")
        if value < 1:
            raise serializers.ValidationError(
                "review_threshold must be at least 1."
            )
        return value

    def validate_verification_threshold(self, value):
        if value is None:
            raise serializers.ValidationError(
                "verification_threshold is required."
            )
        if value < 1:
            raise serializers.ValidationError(
                "verification_threshold must be at least 1."
            )
        return value

    def validate(self, attrs):
        county_type = attrs.get(
            "county_type",
            getattr(self.instance, "county_type", None),
        )
        if not county_type:
            raise serializers.ValidationError(
                {"county_type": ["This field is required."]}
            )

        qs = LongDistanceRule.objects.filter(county_type=county_type)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {
                    "county_type": [
                        "A rule for this county_type already exists."
                    ]
                }
            )
        return attrs


class LongDistanceRuleListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LongDistanceRule
        fields = (
            "id",
            "county_type",
            "review_threshold",
            "verification_threshold",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class LongDistanceRuleIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
