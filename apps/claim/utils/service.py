"""Claim domain services."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum

from apps.claim.choices import (
    AttachmentRoute,
    AttachmentStatus,
    ClaimStatus,
    DocumentStatus,
    DocumentType,
)
from apps.claim.models import BatchClaim, Claim, ClaimDocument, SubmissionBatch
from apps.claim_service_line.models import ClaimServiceLine
from apps.long_distance_rule.utils.service import evaluate_trip_mileage
from apps.nemt_trip.models import NemtTrip

# Required package for long-distance / attachment_required claims (Ali 78-mile path).
REQUIRED_LONG_DISTANCE_DOC_TYPES = (
    DocumentType.STANDARD_TRIP_LOG,
    DocumentType.MILE_25_VERIFICATION,
)


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


def document_is_ready(doc):
    return (
        doc is not None
        and doc.is_active
        and doc.status == DocumentStatus.COMPLETE
        and bool(doc.is_signed)
    )


def evaluate_claim_documents(claim):
    """
    Return completeness snapshot for a claim.
    Long-distance claims need trip log + 25+ verification, both signed COMPLETE.
    """
    required = []
    if claim.attachment_required:
        required = list(REQUIRED_LONG_DISTANCE_DOC_TYPES)

    docs = {
        d.document_type: d
        for d in ClaimDocument.objects.filter(claim_id=claim.id, is_active=True)
        if d.document_type
    }

    missing = []
    incomplete = []
    for doc_type in required:
        doc = docs.get(doc_type)
        if doc is None:
            missing.append(doc_type)
        elif not document_is_ready(doc):
            incomplete.append(doc_type)

    complete = not missing and not incomplete
    return {
        "attachment_required": claim.attachment_required,
        "required_types": required,
        "missing_types": missing,
        "incomplete_types": incomplete,
        "documents_complete": complete if required else True,
        "can_submit": (not claim.attachment_required) or complete,
    }


@transaction.atomic
def sync_claim_document_status(claim):
    """
    Flip claim status from documents:
    - incomplete long-distance package → DOCUMENTS_REQUIRED (blocked)
    - complete package → READY_FOR_837P
    Does not downgrade claims already past READY_FOR_837P / EDI statuses.
    """
    if claim is None:
        return None

    claim = Claim.objects.select_for_update().filter(pk=claim.pk).first()
    if claim is None:
        return None

    snapshot = evaluate_claim_documents(claim)
    terminal = {
        ClaimStatus.EDI_ACCEPTED,
        ClaimStatus.UNDER_REVIEW,
        ClaimStatus.PAID,
        ClaimStatus.DENIED,
        ClaimStatus.ATTACHMENT_QUEUED,
        ClaimStatus.ATTACHMENT_SUBMITTED,
        ClaimStatus.ATTACHMENT_CONFIRMED,
    }
    if claim.status in terminal:
        return snapshot

    if not claim.attachment_required:
        if claim.status in (
            ClaimStatus.DRAFT,
            ClaimStatus.DOCUMENTS_REQUIRED,
            ClaimStatus.DOCUMENTS_COMPLETE,
            None,
            "",
        ):
            claim.status = ClaimStatus.READY_FOR_837P
            claim.save(update_fields=["status", "updated_at"])
        return snapshot

    if snapshot["documents_complete"]:
        claim.status = ClaimStatus.READY_FOR_837P
        claim.save(update_fields=["status", "updated_at"])
    else:
        claim.status = ClaimStatus.DOCUMENTS_REQUIRED
        claim.save(update_fields=["status", "updated_at"])
    return snapshot


def assert_claim_ready_for_batch(claim):
    """Raise ValueError if claim cannot enter an EDI batch (docs incomplete)."""
    if claim is None or not claim.is_active:
        raise ValueError("Claim not found or inactive.")

    sync_claim_document_status(claim)
    claim.refresh_from_db()
    snapshot = evaluate_claim_documents(claim)
    if not snapshot["can_submit"] or claim.status == ClaimStatus.DOCUMENTS_REQUIRED:
        missing = snapshot["missing_types"] + snapshot["incomplete_types"]
        raise ValueError(
            "Claim documents incomplete; submission blocked. "
            f"Needs: {', '.join(missing) or 'required signed documents'}."
        )
    return snapshot


def refresh_batch_totals(batch):
    """Recompute claim_count and total_amount from active BatchClaim rows."""
    if batch is None:
        return None
    agg = BatchClaim.objects.filter(batch_id=batch.id, is_active=True).aggregate(
        count=Count("id"),
        total=Sum("claim__total_charge"),
    )
    batch.claim_count = agg["count"] or 0
    batch.total_amount = agg["total"] or Decimal("0.00")
    batch.save(update_fields=["claim_count", "total_amount", "updated_at"])
    return batch


def next_st02_for_batch(batch):
    """Allocate next ST02 as zero-padded 4-digit sequence within the batch."""
    existing = (
        BatchClaim.objects.filter(batch_id=batch.id, is_active=True)
        .exclude(st02__isnull=True)
        .exclude(st02="")
        .values_list("st02", flat=True)
    )
    max_n = 0
    for value in existing:
        if str(value).isdigit():
            max_n = max(max_n, int(value))
    return f"{max_n + 1:04d}"


@transaction.atomic
def add_claim_to_batch(*, batch_id, claim_id, st02=None):
    batch = (
        SubmissionBatch.objects.select_for_update()
        .filter(pk=batch_id, is_active=True)
        .first()
    )
    if batch is None:
        raise ValueError("Batch not found or inactive.")

    claim = Claim.objects.select_for_update().filter(pk=claim_id, is_active=True).first()
    if claim is None:
        raise ValueError("Claim not found or inactive.")

    assert_claim_ready_for_batch(claim)

    if BatchClaim.objects.filter(batch_id=batch.id, claim_id=claim.id).exists():
        raise ValueError("Claim is already in this batch.")

    st02 = (st02 or "").strip() or next_st02_for_batch(batch)
    if BatchClaim.objects.filter(batch_id=batch.id, st02=st02).exists():
        raise ValueError(f"ST02 {st02} is already used in this batch.")

    row = BatchClaim.objects.create(
        batch=batch,
        claim=claim,
        st02=st02,
        is_active=True,
    )
    refresh_batch_totals(batch)
    return row


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
