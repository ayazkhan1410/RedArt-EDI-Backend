from rest_framework import serializers

from apps.nemt_trip.models import NemtTrip
from apps.nemt_trip.utils.validators import clean_optional_text, ensure_non_negative

WRITE_FIELDS = (
    "patient",
    "provider",
    "service_date",
    "pickup",
    "dropoff",
    "one_way_miles",
    "mileage_units",
    "charge",
    "is_active",
)


class NemtTripSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField(read_only=True)
    provider_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NemtTrip
        fields = (
            "id",
            "patient",
            "patient_name",
            "provider",
            "provider_name",
            "service_date",
            "pickup",
            "dropoff",
            "one_way_miles",
            "mileage_units",
            "charge",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "patient_name",
            "provider_name",
            "created_at",
            "updated_at",
        )

    def get_patient_name(self, obj):
        if not obj.patient_id:
            return None
        return f"{obj.patient.first_name} {obj.patient.last_name}".strip()

    def get_provider_name(self, obj):
        if not obj.provider_id:
            return None
        return obj.provider.billing_name or obj.provider.legal_name

    def validate_patient(self, value):
        # PrimaryKeyRelatedField already loaded the row — no second query.
        if value is None:
            return value
        if not value.is_active:
            raise serializers.ValidationError("Patient not found or inactive.")
        return value

    def validate_provider(self, value):
        if value is None:
            return value
        if not value.is_active:
            raise serializers.ValidationError(
                "Provider billing profile not found or inactive."
            )
        return value

    def validate_pickup(self, value):
        return clean_optional_text(value)

    def validate_dropoff(self, value):
        return clean_optional_text(value)

    def validate_one_way_miles(self, value):
        return ensure_non_negative(value, "one_way_miles")

    def validate_mileage_units(self, value):
        if value is None:
            return value
        if value < 0:
            raise serializers.ValidationError("mileage_units cannot be negative.")
        return value

    def validate_charge(self, value):
        return ensure_non_negative(value, "charge")

    def validate(self, attrs):
        pickup = attrs.get("pickup", getattr(self.instance, "pickup", None))
        dropoff = attrs.get("dropoff", getattr(self.instance, "dropoff", None))
        if pickup and dropoff and pickup.casefold() == dropoff.casefold():
            raise serializers.ValidationError(
                {
                    "dropoff": [
                        "dropoff should differ from pickup for a billable trip."
                    ]
                }
            )
        return attrs


class NemtTripListSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    provider_name = serializers.SerializerMethodField()

    class Meta:
        model = NemtTrip
        fields = (
            "id",
            "patient",
            "patient_name",
            "provider",
            "provider_name",
            "service_date",
            "pickup",
            "dropoff",
            "one_way_miles",
            "mileage_units",
            "charge",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    def get_patient_name(self, obj):
        if not obj.patient_id:
            return None
        return f"{obj.patient.first_name} {obj.patient.last_name}".strip()

    def get_provider_name(self, obj):
        if not obj.provider_id:
            return None
        return obj.provider.billing_name or obj.provider.legal_name


class NemtTripIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class LongDistanceCheckSerializer(serializers.Serializer):
    county = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    county_type = serializers.CharField()
    verification_threshold = serializers.FloatField()
    review_threshold = serializers.IntegerField()
    one_way_miles = serializers.FloatField(allow_null=True)
    mileage_units = serializers.IntegerField(allow_null=True)
    verification_25_required = serializers.BooleanField()
    long_distance_review = serializers.BooleanField()
    attachment_required = serializers.BooleanField()
