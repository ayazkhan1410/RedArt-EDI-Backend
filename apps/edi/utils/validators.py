"""Field cleaners for EDI APIs."""

from rest_framework import serializers


def clean_optional_text(value):
    if value is None:
        return value
    value = str(value).strip()
    return value or None


def clean_control_digits(value, field_name, *, max_length=9, pad_to=None):
    if value in (None, ""):
        return None
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if not digits:
        raise serializers.ValidationError(f"{field_name} must be numeric.")
    if len(digits) > max_length:
        raise serializers.ValidationError(
            f"{field_name} must be at most {max_length} digits."
        )
    if pad_to:
        digits = digits.zfill(pad_to)
    return digits
