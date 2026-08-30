"""
Pure mileage math for Colorado NEMT long-distance checks.

DB thresholds live on LongDistanceRule; these defaults are fallbacks only.
"""

from decimal import Decimal

DEFAULT_VERIFICATION_THRESHOLD = Decimal("25")
DEFAULT_STANDARD_REVIEW_THRESHOLD = 52
DEFAULT_RURAL_REVIEW_THRESHOLD = 125


def _as_decimal(value):
    if value is None:
        return None
    return Decimal(str(value))


def requires_25_plus_verification(one_way_miles, threshold=None):
    miles = _as_decimal(one_way_miles)
    if miles is None:
        return False
    limit = (
        DEFAULT_VERIFICATION_THRESHOLD
        if threshold is None
        else _as_decimal(threshold)
    )
    return miles > limit


def requires_long_distance_review(mileage_units, review_threshold):
    if mileage_units is None or review_threshold is None:
        return False
    try:
        units = int(mileage_units)
        threshold = int(review_threshold)
    except (TypeError, ValueError):
        return False
    return units > threshold
