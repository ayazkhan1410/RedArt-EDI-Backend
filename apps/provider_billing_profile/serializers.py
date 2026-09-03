from rest_framework import serializers

from apps.provider_billing_profile.models import ProviderBillingProfile

WRITE_FIELDS = (
    "legal_name",
    "billing_name",
    "npi",
    "tax_id",
    "is_atypical",
    "taxonomy_code",
    "location_id",
    "medicaid_provider_id",
    "revalidation_date",
    "city",
    "zip",
    "state",
    "country",
    "address_line_1",
    "address_line_2",
    "phone",
    "email",
    "is_active",
)


def clean_optional_text(value):
    if value is None:
        return value
    value = value.strip()
    return value or None


class ProviderBillingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderBillingProfile
        fields = ("id",) + WRITE_FIELDS + ("created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_legal_name(self, value):
        return clean_optional_text(value)

    def validate_billing_name(self, value):
        return clean_optional_text(value)

    def validate_npi(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        if not value.isdigit():
            raise serializers.ValidationError("NPI must contain digits only.")
        if len(value) > 10:
            raise serializers.ValidationError("NPI must be at most 10 digits.")
        return value

    def validate_tax_id(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            raise serializers.ValidationError("tax_id must contain at least one digit.")
        if len(digits) > 9:
            raise serializers.ValidationError("tax_id (EIN/TIN) must be at most 9 digits.")
        return digits  # store digits only

    def validate_taxonomy_code(self, value):
        return clean_optional_text(value)

    def validate_location_id(self, value):
        return clean_optional_text(value)

    def validate_medicaid_provider_id(self, value):
        return clean_optional_text(value)

    def validate_city(self, value):
        return clean_optional_text(value)

    def validate_zip(self, value):
        return clean_optional_text(value)

    def validate_state(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        return value.upper()

    def validate_country(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        return value.upper()

    def validate_address_line_1(self, value):
        return clean_optional_text(value)

    def validate_address_line_2(self, value):
        return clean_optional_text(value)

    def validate_phone(self, value):
        return clean_optional_text(value)

    def validate_email(self, value):
        return clean_optional_text(value)

    def validate(self, attrs):
        is_atypical = attrs.get(
            "is_atypical",
            getattr(self.instance, "is_atypical", False),
        )
        npi = (attrs.get("npi") or getattr(self.instance, "npi", None) or "").strip()
        medicaid_provider_id = (
            attrs.get("medicaid_provider_id")
            or getattr(self.instance, "medicaid_provider_id", None)
            or ""
        ).strip()

        if is_atypical:
            if not medicaid_provider_id:
                raise serializers.ValidationError(
                    {
                        "medicaid_provider_id": [
                            "medicaid_provider_id is required for atypical providers "
                            "(is_atypical=True)."
                        ]
                    }
                )
            if npi:
                raise serializers.ValidationError(
                    {
                        "npi": [
                            "Atypical providers must not have an NPI. "
                            "Clear npi or set is_atypical=False."
                        ]
                    }
                )
        return attrs


class ProviderBillingProfileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderBillingProfile
        fields = (
            "id",
            "legal_name",
            "billing_name",
            "npi",
            "is_atypical",
            "medicaid_provider_id",
            "location_id",
            "city",
            "state",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class ProviderBillingProfileIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
