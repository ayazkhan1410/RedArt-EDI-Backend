"""Domain services for NEMT trips (not serializers)."""

from apps.long_distance_rule.utils.service import evaluate_trip_mileage


def build_long_distance_payload(trip):
    """
    Build long-distance / attachment flags for a trip using patient county
    and trip mileage fields against LongDistanceRule rows.
    """
    county = None
    if trip.patient_id:
        county = trip.patient.county
    return evaluate_trip_mileage(
        one_way_miles=trip.one_way_miles,
        mileage_units=trip.mileage_units,
        county=county,
    )
