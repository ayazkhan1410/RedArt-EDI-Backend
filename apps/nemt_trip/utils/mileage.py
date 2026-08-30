"""
Mileage / long-distance helpers for Colorado NEMT.

Thresholds follow the HCPF NEMT billing guidance summarized in the
RedArt 52+ attachment workflow guide. When LongDistanceRule exists,
call sites can pass explicit thresholds instead of these defaults.
"""

from decimal import Decimal

DEFAULT_VERIFICATION_THRESHOLD = Decimal("25")
DEFAULT_STANDARD_REVIEW_THRESHOLD = 52
DEFAULT_RURAL_REVIEW_THRESHOLD = 125

# Fill from LongDistanceRule / config later. Matching is case-insensitive.
DESIGNATED_RURAL_COUNTIES = frozenset()


def _as_decimal(value):
    if value is None:
        return None
    return Decimal(str(value))


def normalize_county(county):
    if county is None:
        return None
    county = str(county).strip()
    return county or None


def is_designated_rural_county(county):
    county = normalize_county(county)
    if not county:
        return False
    return county.casefold() in {c.casefold() for c in DESIGNATED_RURAL_COUNTIES}


def resolve_review_threshold(county=None, rural_counties=None):
    """
    Return (county_type, review_threshold).
    STANDARD -> 52, DESIGNATED_RURAL -> 125.
    """
    counties = (
        DESIGNATED_RURAL_COUNTIES
        if rural_counties is None
        else frozenset(rural_counties)
    )
    county = normalize_county(county)
    if county and county.casefold() in {c.casefold() for c in counties}:
        return "DESIGNATED_RURAL", DEFAULT_RURAL_REVIEW_THRESHOLD
    return "STANDARD", DEFAULT_STANDARD_REVIEW_THRESHOLD


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


def evaluate_trip_mileage(
    *,
    one_way_miles=None,
    mileage_units=None,
    county=None,
    verification_threshold=None,
    rural_counties=None,
):
    """
    Decide document / attachment flags for a trip before claim submit.
    Does not invent signatures or documents — only rules output.
    """
    county_type, review_threshold = resolve_review_threshold(
        county=county,
        rural_counties=rural_counties,
    )
    verification_required = requires_25_plus_verification(
        one_way_miles,
        threshold=verification_threshold,
    )
    long_distance_review = requires_long_distance_review(
        mileage_units,
        review_threshold,
    )
    return {
        "county": normalize_county(county),
        "county_type": county_type,
        "verification_threshold": float(
            verification_threshold
            if verification_threshold is not None
            else DEFAULT_VERIFICATION_THRESHOLD
        ),
        "review_threshold": review_threshold,
        "one_way_miles": (
            float(_as_decimal(one_way_miles))
            if one_way_miles is not None
            else None
        ),
        "mileage_units": (
            int(mileage_units) if mileage_units is not None else None
        ),
        "verification_25_required": verification_required,
        "long_distance_review": long_distance_review,
        "attachment_required": long_distance_review,
    }
