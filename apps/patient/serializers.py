from datetime import date

from rest_framework import serializers

from apps.patient.choices import Gender
from apps.patient.models import Patient

WRITE_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "date_of_birth",
    "gender",
    "medicaid_member_id",
    "county",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "zip",
    "phone",
    "is_active",
)


def clean_required_text(value, field_name):
    if value is None:
        raise serializers.ValidationError(f"{field_name} is required.")
    value = value.strip()
    if not value:
        raise serializers.ValidationError(f"{field_name} cannot be blank.")
    return value


def clean_optional_text(value):
    if value is None:
        return value
    value = value.strip()
    return value or None


class PatientSerializer(serializers.ModelSerializer):
    gender = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = Patient
        fields = ("id",) + WRITE_FIELDS + ("created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_first_name(self, value):
        return clean_required_text(value, "first_name")

    def validate_last_name(self, value):
        return clean_required_text(value, "last_name")

    def validate_email(self, value):
        return clean_optional_text(value)

    def validate_medicaid_member_id(self, value):
        value = clean_required_text(value, "medicaid_member_id")
        return value.upper()

    def validate_county(self, value):
        return clean_required_text(value, "county")

    def validate_gender(self, value):
        if value in (None, ""):
            return None
        value = str(value).strip().upper()
        if value not in Gender.values:
            raise serializers.ValidationError("Invalid gender. Use M, F, or U.")
        return value

    def validate_address_line_1(self, value):
        return clean_optional_text(value)

    def validate_address_line_2(self, value):
        return clean_optional_text(value)

    def validate_city(self, value):
        return clean_optional_text(value)

    def validate_state(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        value = value.upper()
        if len(value) != 2:
            raise serializers.ValidationError("state must be a 2-letter code.")
        return value

    def validate_zip(self, value):
        return clean_optional_text(value)

    def validate_phone(self, value):
        return clean_optional_text(value)

    def validate_date_of_birth(self, value):
        if value is None:
            raise serializers.ValidationError("date_of_birth is required.")
        if value > date.today():
            raise serializers.ValidationError("date_of_birth cannot be in the future.")
        return value

    def validate(self, attrs):
        medicaid_member_id = attrs.get(
            "medicaid_member_id",
            getattr(self.instance, "medicaid_member_id", None),
        )
        if medicaid_member_id:
            qs = Patient.objects.filter(medicaid_member_id__iexact=medicaid_member_id)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "medicaid_member_id": [
                            "A patient with this medicaid_member_id already exists."
                        ]
                    }
                )
        return attrs


class PatientListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = (
            "id",
            "first_name",
            "last_name",
            "medicaid_member_id",
            "county",
            "city",
            "state",
            "gender",
            "date_of_birth",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class PatientIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
