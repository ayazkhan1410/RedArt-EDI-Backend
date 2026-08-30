"""Shared field cleaning helpers used by serializers and views."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from rest_framework import serializers
from rest_framework.exceptions import ValidationError


def clean_optional_text(value):
    if value is None:
        return value
    value = str(value).strip()
    return value or None


def ensure_non_negative(value, field_name):
    if value is None:
        return value
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise serializers.ValidationError(f"{field_name} must be a valid number.")
    if number < 0:
        raise serializers.ValidationError(f"{field_name} cannot be negative.")
    return number


def parse_optional_date(raw, field_name):
    if raw in (None, ""):
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError({field_name: ["Use YYYY-MM-DD format."]})


def parse_optional_int(raw, field_name):
    if raw in (None, ""):
        return None
    if not str(raw).isdigit():
        raise ValidationError({field_name: ["Must be a positive whole number."]})
    value = int(raw)
    if value < 1:
        raise ValidationError({field_name: ["Must be a positive whole number."]})
    return value
