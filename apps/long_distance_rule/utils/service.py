"""Domain services for long-distance rule lookup and evaluation."""

from decimal import Decimal

from apps.long_distance_rule.choices import CountyType
from apps.long_distance_rule.models import LongDistanceRule
from apps.long_distance_rule.utils.counties import (
    normalize_county,
    resolve_county_type,
)
from apps.nemt_trip.utils.mileage import (
    DEFAULT_RURAL_REVIEW_THRESHOLD,
    DEFAULT_STANDARD_REVIEW_THRESHOLD,
    DEFAULT_VERIFICATION_THRESHOLD,
    requires_25_plus_verification,
    requires_long_distance_review,
)


def get_active_rules_by_county_type():
    return {
        rule.county_type: rule
        for rule in LongDistanceRule.objects.filter(is_active=True)
        if rule.county_type
    }


def get_rule_for_county_type(county_type, rules=None):
    rules = get_active_rules_by_county_type() if rules is None else rules
    rule = rules.get(county_type)
    if rule is None and county_type != CountyType.STANDARD:
        rule = rules.get(CountyType.STANDARD)
    return rule


def thresholds_from_rule(rule, county_type):
    if rule and rule.review_threshold is not None:
        review_threshold = int(rule.review_threshold)
    elif county_type == CountyType.DESIGNATED_RURAL:
        review_threshold = DEFAULT_RURAL_REVIEW_THRESHOLD
    else:
        review_threshold = DEFAULT_STANDARD_REVIEW_THRESHOLD

    if rule and rule.verification_threshold is not None:
        verification_threshold = Decimal(str(rule.verification_threshold))
    else:
        verification_threshold = DEFAULT_VERIFICATION_THRESHOLD

    return review_threshold, verification_threshold


def evaluate_trip_mileage(
    *,
    one_way_miles=None,
    mileage_units=None,
    county=None,
    rural_counties=None,
):
    """
    Decide document / attachment flags using DB LongDistanceRule rows.
    Falls back to HCPF defaults only if an active rule row is missing.
    """
    county_type = resolve_county_type(county, rural_counties=rural_counties)
    rules = get_active_rules_by_county_type()
    rule = get_rule_for_county_type(county_type, rules=rules)
    review_threshold, verification_threshold = thresholds_from_rule(
        rule, county_type
    )

    verification_required = requires_25_plus_verification(
        one_way_miles,
        threshold=verification_threshold,
    )
    long_distance_review = requires_long_distance_review(
        mileage_units,
        review_threshold,
    )

    miles = None
    if one_way_miles is not None:
        miles = float(Decimal(str(one_way_miles)))

    return {
        "county": normalize_county(county),
        "county_type": county_type,
        "rule_id": rule.id if rule else None,
        "verification_threshold": float(verification_threshold),
        "review_threshold": review_threshold,
        "one_way_miles": miles,
        "mileage_units": (
            int(mileage_units) if mileage_units is not None else None
        ),
        "verification_25_required": verification_required,
        "long_distance_review": long_distance_review,
        "attachment_required": long_distance_review,
    }
