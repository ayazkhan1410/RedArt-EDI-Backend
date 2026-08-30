"""Claim domain services."""

from django.db import transaction

from apps.claim.choices import AttachmentRoute, AttachmentStatus, ClaimStatus
from apps.claim.models import Claim
from apps.claim_service_line.models import ClaimServiceLine
from apps.long_distance_rule.utils.service import evaluate_trip_mileage
from apps.nemt_trip.models import NemtTrip


def apply_long_distance_flags(claim, trip):
    """
    Set attachment flags once from trip mileage rules.
    Call at create/update-from-trip time — do not re-decide after 999.
    """
    county = None
    if trip.patient_id:
        county = trip.patient.county

    result = evaluate_trip_mileage(
        one_way_miles=trip.one_way_miles,
        mileage_units=trip.mileage_units,
        county=county,
    )
    claim.attachment_required = bool(result["attachment_required"])
    if claim.attachment_required:
        claim.attachment_route = AttachmentRoute.HCPF_APPROVED_CHANNEL
        claim.attachment_status = AttachmentStatus.PENDING
        if claim.status in (None, ClaimStatus.DRAFT, ""):
            claim.status = ClaimStatus.DOCUMENTS_REQUIRED
    else:
        claim.attachment_route = AttachmentRoute.NONE
        claim.attachment_status = AttachmentStatus.NOT_REQUIRED
        if claim.status in (None, ClaimStatus.DRAFT, ""):
            claim.status = ClaimStatus.READY_FOR_837P
    return result


@transaction.atomic
def create_claim_from_trip(
    *,
    trip_id,
    claim_number=None,
    external_id=None,
    diagnosis_code=None,
    place_of_service=None,
    procedure_code="A0100",
    create_service_line=True,
):
    """
    Create a claim (and optional demo service line) from an existing trip.
    Enforces one active claim per trip via DB unique constraint.
    """
    trip = NemtTrip.objects.with_relations().filter(pk=trip_id, is_active=True).first()
    if trip is None:
        raise ValueError("Trip not found or inactive.")

    if Claim.objects.filter(trip_id=trip.id).exists():
        raise ValueError("A claim already exists for this trip.")

    claim = Claim(
        claim_number=claim_number,
        external_id=external_id,
        trip=trip,
        diagnosis_code=diagnosis_code,
        place_of_service=place_of_service,
        total_charge=trip.charge,
        is_active=True,
    )
    apply_long_distance_flags(claim, trip)
    claim.save()

    line = None
    if create_service_line:
        line = ClaimServiceLine.objects.create(
            claim=claim,
            procedure_code=procedure_code,
            from_date=trip.service_date,
            to_date=trip.service_date,
            units=trip.mileage_units,
            mileage=trip.one_way_miles,
            charge=trip.charge,
            is_active=True,
        )

    return claim, line
