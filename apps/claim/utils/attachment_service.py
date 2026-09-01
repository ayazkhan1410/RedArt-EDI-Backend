"""Attachment queue, dashboard aggregates, duplicate guards, and live submit."""

from __future__ import annotations

import hashlib
import logging

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.claim.choices import (
    AttachmentRoute,
    AttachmentStatus,
    AttachmentSubmissionStatus,
    ClaimStatus,
    DocumentStatus,
    DocumentType,
)
from apps.claim.models import AttachmentSubmission, Claim, ClaimDocument
from apps.claim.utils.attachment_adapter import get_attachment_adapter, load_transmit_documents
from apps.claim.utils.service import (
    assert_claim_ready_for_batch,
    evaluate_claim_documents,
    sync_claim_document_status,
    sync_claim_from_attachment_submission,
)

logger = logging.getLogger(__name__)

ACTIVE_TRANSMISSION_STATUSES = (
    AttachmentSubmissionStatus.QUEUED,
    AttachmentSubmissionStatus.SUBMITTED,
    AttachmentSubmissionStatus.CONFIRMED,
)


def compute_claim_document_payload_hash(claim_id: int) -> str | None:
    """
    Stable hash of complete active documents on a claim.
    Used to block duplicate attachment transmissions.
    """
    rows = (
        ClaimDocument.objects.filter(
            claim_id=claim_id,
            is_active=True,
            status=DocumentStatus.COMPLETE,
        )
        .exclude(document_hash__isnull=True)
        .exclude(document_hash="")
        .order_by("document_type")
        .values_list("document_type", "document_hash", "blob_ref")
    )
    if not rows:
        return None

    parts = []
    for doc_type, doc_hash, blob_ref in rows:
        blob = (blob_ref or "").strip()
        parts.append(f"{doc_type}:{doc_hash}:{blob}")

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest


def find_duplicate_attachment_submission(claim_id: int, payload_hash: str | None):
    if not payload_hash:
        return None
    return (
        AttachmentSubmission.objects.filter(
            claim_id=claim_id,
            is_active=True,
            payload_hash=payload_hash,
            status__in=ACTIVE_TRANSMISSION_STATUSES,
        )
        .order_by("-id")
        .first()
    )


def assert_no_duplicate_attachment_submission(claim_id: int, payload_hash: str | None):
    duplicate = find_duplicate_attachment_submission(claim_id, payload_hash)
    if duplicate is None:
        return None
    raise ValueError(
        "Duplicate attachment transmission blocked. "
        f"An active submission already exists (id={duplicate.id}, "
        f"status={duplicate.status}, reference={duplicate.submission_reference})."
    )


def build_attachment_queue_row(claim: Claim) -> dict:
    snapshot = evaluate_claim_documents(claim)
    trip = claim.trip if claim.trip_id else None
    return {
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "external_id": claim.external_id,
        "status": claim.status,
        "attachment_status": claim.attachment_status,
        "attachment_route": claim.attachment_route,
        "patient_id": trip.patient_id if trip else None,
        "provider_id": trip.provider_id if trip else None,
        "mileage_units": trip.mileage_units if trip else None,
        "one_way_miles": (
            float(trip.one_way_miles) if trip and trip.one_way_miles is not None else None
        ),
        **snapshot,
    }


def list_attachment_queue(
    *,
    documents_complete: bool | None = None,
    can_submit: bool | None = None,
):
    claims = (
        Claim.objects.filter(is_active=True, attachment_required=True)
        .with_relations()
        .order_by("-id")
    )
    rows = [build_attachment_queue_row(c) for c in claims]

    if documents_complete is not None:
        rows = [r for r in rows if r["documents_complete"] == documents_complete]
    if can_submit is not None:
        rows = [r for r in rows if r["can_submit"] == can_submit]

    return rows


def build_attachment_dashboard() -> dict:
    base = Claim.objects.filter(is_active=True, attachment_required=True)

    long_distance_claims = base.count()

    docs_complete_ids = set()
    missing_verification = 0
    missing_trip_log = 0
    missing_signature = 0

    for claim in base.only("id", "attachment_required"):
        snapshot = evaluate_claim_documents(claim)
        if snapshot["documents_complete"]:
            docs_complete_ids.add(claim.id)
        missing = set(snapshot["missing_types"])
        incomplete = set(snapshot["incomplete_types"])
        if DocumentType.MILE_25_VERIFICATION in missing:
            missing_verification += 1
        if DocumentType.STANDARD_TRIP_LOG in missing:
            missing_trip_log += 1
        unsigned = ClaimDocument.objects.filter(
            claim_id=claim.id,
            is_active=True,
            document_type__in=(
                DocumentType.STANDARD_TRIP_LOG,
                DocumentType.MILE_25_VERIFICATION,
            ),
            is_signed=False,
        ).exists()
        if unsigned or (
            DocumentType.MILE_25_VERIFICATION in incomplete
            or DocumentType.STANDARD_TRIP_LOG in incomplete
        ):
            missing_signature += 1

    ready_with_documents = len(docs_complete_ids)

    attachment_qs = AttachmentSubmission.objects.filter(
        claim__in=base.values("id"),
        is_active=True,
    )
    status_counts = attachment_qs.values("status").annotate(count=Count("id"))
    by_status = {row["status"]: row["count"] for row in status_counts}

    submitted = (
        by_status.get(AttachmentSubmissionStatus.SUBMITTED, 0)
        + by_status.get(AttachmentSubmissionStatus.CONFIRMED, 0)
    )
    awaiting_confirmation = base.filter(
        attachment_status__in=(
            AttachmentStatus.QUEUED,
            AttachmentStatus.SUBMITTED,
            AttachmentStatus.PENDING,
        ),
        status__in=(
            ClaimStatus.ATTACHMENT_QUEUED,
            ClaimStatus.ATTACHMENT_SUBMITTED,
            ClaimStatus.ATTACHMENT_REQUIRED,
            ClaimStatus.READY_FOR_837P,
            ClaimStatus.DOCUMENTS_COMPLETE,
        ),
    ).count()

    confirmed = base.filter(
        attachment_status=AttachmentStatus.CONFIRMED,
    ).count()
    failed = base.filter(attachment_status=AttachmentStatus.FAILED).count()
    blocked_from_batch = base.filter(status=ClaimStatus.DOCUMENTS_REQUIRED).count()

    return {
        "long_distance_claims": long_distance_claims,
        "ready_with_documents": ready_with_documents,
        "documents_complete": ready_with_documents,
        "missing_verification": missing_verification,
        "missing_trip_log": missing_trip_log,
        "missing_signature": missing_signature,
        "submitted": submitted,
        "awaiting_confirmation": awaiting_confirmation,
        "confirmed": confirmed,
        "failed": failed,
        "blocked_from_batch": blocked_from_batch,
        "attachment_submissions_by_status": by_status,
    }


@transaction.atomic
def submit_claim_attachments(
    claim_id: int,
    *,
    channel: str | None = None,
    submission_reference: str | None = None,
    environment: str | None = None,
    allow_retry: bool = False,
) -> AttachmentSubmission:
    """
    Validate docs, guard duplicates, run adapter, persist AttachmentSubmission.
    """
    claim = (
        Claim.objects.select_for_update()
        .filter(pk=claim_id, is_active=True)
        .first()
    )
    if claim is None:
        raise ValueError("Claim not found or inactive.")
    if not claim.attachment_required:
        raise ValueError("Claim does not require attachments.")

    sync_claim_document_status(claim)
    claim.refresh_from_db()
    assert_claim_ready_for_batch(claim)

    documents = load_transmit_documents(claim.id)
    if not documents:
        raise ValueError(
            "No stored document files found. Upload PDFs before attachment submit."
        )

    payload_hash = compute_claim_document_payload_hash(claim.id)
    duplicate = find_duplicate_attachment_submission(claim.id, payload_hash)
    if duplicate is not None:
        assert_no_duplicate_attachment_submission(claim.id, payload_hash)

    if allow_retry and payload_hash:
        failed_row = (
            AttachmentSubmission.objects.filter(
                claim_id=claim.id,
                is_active=True,
                payload_hash=payload_hash,
                status=AttachmentSubmissionStatus.FAILED,
            )
            .order_by("-id")
            .first()
        )
        if failed_row is not None:
            failed_row.retry_count = (failed_row.retry_count or 0) + 1
            failed_row.is_active = False
            failed_row.save(update_fields=["retry_count", "is_active", "updated_at"])

    route = (channel or claim.attachment_route or AttachmentRoute.HCPF_PORTAL).strip().upper()
    adapter = get_attachment_adapter(route)
    result = adapter.transmit(
        claim,
        documents,
        submission_reference=submission_reference,
        environment=environment,
    )

    submission = AttachmentSubmission.objects.create(
        claim=claim,
        channel=route,
        submission_reference=result.submission_reference,
        payload_hash=payload_hash,
        remote_path=result.remote_path,
        status=result.status,
        notes=result.notes,
        submitted_at=(
            timezone.now()
            if result.status in (
                AttachmentSubmissionStatus.SUBMITTED,
                AttachmentSubmissionStatus.CONFIRMED,
            )
            else None
        ),
        is_active=True,
    )
    sync_claim_from_attachment_submission(submission)
    logger.info(
        "Attachment submit claim_id=%s submission_id=%s channel=%s status=%s",
        claim.id,
        submission.id,
        route,
        result.status,
    )
    return submission


@transaction.atomic
def upsert_claim_document_from_upload(
    *,
    claim: Claim,
    document_type: str,
    file_name: str,
    document_hash: str,
    blob_ref: str,
    content_type: str,
    file_size: int,
    is_signed: bool = False,
    status: str | None = None,
) -> ClaimDocument:
    """Create or replace the active document row for a claim document type."""
    status = status or DocumentStatus.COMPLETE
    existing = ClaimDocument.objects.filter(
        claim_id=claim.id,
        document_type=document_type,
        is_active=True,
    ).first()

    if existing is not None:
        existing.file_name = file_name
        existing.document_hash = document_hash
        existing.blob_ref = blob_ref
        existing.content_type = content_type
        existing.file_size = file_size
        existing.is_signed = is_signed
        existing.status = status
        existing.save(
            update_fields=[
                "file_name",
                "document_hash",
                "blob_ref",
                "content_type",
                "file_size",
                "is_signed",
                "status",
                "updated_at",
            ]
        )
        doc = existing
    else:
        doc = ClaimDocument.objects.create(
            claim=claim,
            document_type=document_type,
            file_name=file_name,
            document_hash=document_hash,
            blob_ref=blob_ref,
            content_type=content_type,
            file_size=file_size,
            is_signed=is_signed,
            status=status,
            is_active=True,
        )

    sync_claim_document_status(claim)
    return doc
