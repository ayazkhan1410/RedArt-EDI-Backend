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
    prefetch_claim_documents_map,
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


def build_attachment_queue_row(claim: Claim, docs_by_type=None) -> dict:
    snapshot = evaluate_claim_documents(claim, docs_by_type=docs_by_type)
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
    """Return queue rows for attachment-required claims (caller paginates queryset)."""
    claims = (
        Claim.objects.filter(is_active=True, attachment_required=True)
        .with_relations()
        .order_by("-id")
    )
    claim_list = list(claims)
    docs_map = prefetch_claim_documents_map([c.id for c in claim_list])
    rows = [
        build_attachment_queue_row(c, docs_map.get(c.id))
        for c in claim_list
    ]

    if documents_complete is not None:
        rows = [r for r in rows if r["documents_complete"] == documents_complete]
    if can_submit is not None:
        rows = [r for r in rows if r["can_submit"] == can_submit]

    return rows


def attachment_queue_claims_queryset():
    """DB queryset for paginated attachment queue (before doc snapshot filters)."""
    return (
        Claim.objects.filter(is_active=True, attachment_required=True)
        .with_relations()
        .order_by("-id")
    )


def build_attachment_queue_page(claims, *, documents_complete=None, can_submit=None):
    """Build queue rows for one paginated page of claims."""
    docs_map = prefetch_claim_documents_map([c.id for c in claims])
    rows = [
        build_attachment_queue_row(c, docs_map.get(c.id))
        for c in claims
    ]
    if documents_complete is not None:
        rows = [r for r in rows if r["documents_complete"] == documents_complete]
    if can_submit is not None:
        rows = [r for r in rows if r["can_submit"] == can_submit]
    return rows


def build_attachment_dashboard() -> dict:
    base = Claim.objects.filter(is_active=True, attachment_required=True)

    long_distance_claims = base.count()
    claim_ids = list(base.values_list("id", flat=True))
    docs_map = prefetch_claim_documents_map(claim_ids)

    docs_complete_ids = set()
    missing_verification = 0
    missing_trip_log = 0
    missing_signature = 0

    for claim in base.only("id", "attachment_required"):
        snapshot = evaluate_claim_documents(
            claim,
            docs_by_type=docs_map.get(claim.id),
        )
        if snapshot["documents_complete"]:
            docs_complete_ids.add(claim.id)
        missing = set(snapshot["missing_types"])
        incomplete = set(snapshot["incomplete_types"])
        if DocumentType.MILE_25_VERIFICATION in missing:
            missing_verification += 1
        if DocumentType.STANDARD_TRIP_LOG in missing:
            missing_trip_log += 1
        claim_docs = docs_map.get(claim.id, {})
        unsigned = any(
            doc.document_type in (
                DocumentType.STANDARD_TRIP_LOG,
                DocumentType.MILE_25_VERIFICATION,
            )
            and not doc.is_signed
            for doc in claim_docs.values()
        )
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
    Network I/O runs outside DB transactions.
    """
    with transaction.atomic():
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
        submission = AttachmentSubmission.objects.create(
            claim=claim,
            channel=route,
            submission_reference=(submission_reference or "").strip() or None,
            payload_hash=payload_hash,
            status=AttachmentSubmissionStatus.QUEUED,
            is_active=True,
        )
        submission_id = submission.id
        route_saved = route

    documents = load_transmit_documents(claim_id)
    if not documents:
        with transaction.atomic():
            submission = AttachmentSubmission.objects.select_for_update().get(pk=submission_id)
            submission.status = AttachmentSubmissionStatus.FAILED
            submission.notes = "No stored document files found."
            submission.save(update_fields=["status", "notes", "updated_at"])
            sync_claim_from_attachment_submission(submission)
        raise ValueError(
            "No stored document files found. Upload PDFs before attachment submit."
        )

    claim = Claim.objects.get(pk=claim_id)
    adapter = get_attachment_adapter(route_saved)
    try:
        result = adapter.transmit(
            claim,
            documents,
            submission_reference=submission_reference,
            environment=environment,
        )
    except Exception as exc:
        with transaction.atomic():
            submission = AttachmentSubmission.objects.select_for_update().get(pk=submission_id)
            submission.status = AttachmentSubmissionStatus.FAILED
            submission.notes = str(exc)[:500]
            submission.save(update_fields=["status", "notes", "updated_at"])
            sync_claim_from_attachment_submission(submission)
        raise

    with transaction.atomic():
        submission = AttachmentSubmission.objects.select_for_update().get(pk=submission_id)
        submission.submission_reference = result.submission_reference
        submission.remote_path = result.remote_path
        submission.status = result.status
        submission.notes = result.notes
        if result.status in (
            AttachmentSubmissionStatus.SUBMITTED,
            AttachmentSubmissionStatus.CONFIRMED,
        ):
            submission.submitted_at = timezone.now()
        submission.save(
            update_fields=[
                "submission_reference",
                "remote_path",
                "status",
                "notes",
                "submitted_at",
                "updated_at",
            ]
        )
        sync_claim_from_attachment_submission(submission)

    logger.info(
        "Attachment submit claim_id=%s submission_id=%s channel=%s status=%s",
        claim_id,
        submission_id,
        route_saved,
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
    service_date=None,
    verification_date=None,
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
        existing.service_date = service_date
        existing.verification_date = verification_date
        existing.save(
            update_fields=[
                "file_name",
                "document_hash",
                "blob_ref",
                "content_type",
                "file_size",
                "is_signed",
                "status",
                "service_date",
                "verification_date",
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
            service_date=service_date,
            verification_date=verification_date,
            is_active=True,
        )

    sync_claim_document_status(claim)
    return doc


@transaction.atomic
def confirm_attachment_submission(
    claim_id: int,
    *,
    submission_id: int | None = None,
    submission_reference: str | None = None,
) -> AttachmentSubmission:
    claim = Claim.objects.select_for_update().filter(pk=claim_id, is_active=True).first()
    if claim is None:
        raise ValueError("Claim not found or inactive.")

    qs = AttachmentSubmission.objects.filter(claim_id=claim.id, is_active=True)
    if submission_id:
        submission = qs.filter(pk=submission_id).first()
    else:
        submission = qs.filter(
            status__in=(
                AttachmentSubmissionStatus.SUBMITTED,
                AttachmentSubmissionStatus.QUEUED,
            )
        ).order_by("-id").first()

    if submission is None:
        raise ValueError("No active attachment submission found to confirm.")

    if submission_reference:
        submission.submission_reference = submission_reference.strip()
    submission.status = AttachmentSubmissionStatus.CONFIRMED
    if submission.submitted_at is None:
        submission.submitted_at = timezone.now()
    submission.confirmed_at = timezone.now()
    submission.save(
        update_fields=[
            "submission_reference",
            "status",
            "submitted_at",
            "confirmed_at",
            "updated_at",
        ]
    )
    sync_claim_from_attachment_submission(submission)
    return submission


@transaction.atomic
def fail_attachment_submission(
    claim_id: int,
    *,
    submission_id: int | None = None,
    notes: str | None = None,
) -> AttachmentSubmission:
    claim = Claim.objects.select_for_update().filter(pk=claim_id, is_active=True).first()
    if claim is None:
        raise ValueError("Claim not found or inactive.")

    qs = AttachmentSubmission.objects.filter(claim_id=claim.id, is_active=True)
    if submission_id:
        submission = qs.filter(pk=submission_id).first()
    else:
        submission = qs.exclude(status=AttachmentSubmissionStatus.CONFIRMED).order_by(
            "-id"
        ).first()

    if submission is None:
        raise ValueError("No active attachment submission found to fail.")

    submission.status = AttachmentSubmissionStatus.FAILED
    if notes:
        submission.notes = notes[:500]
    submission.save(update_fields=["status", "notes", "updated_at"])
    sync_claim_from_attachment_submission(submission)
    return submission


def bulk_review_attachments(items: list[dict]) -> dict:
    """
    Process a batch of attachment review actions for RedArt ops.
    Each item: {claim_id, action, channel?, submission_reference?, environment?, notes?}
    action: SUBMIT | CONFIRM | FAIL
    """
    results = []
    success_count = 0
    error_count = 0

    for item in items:
        claim_id = item.get("claim_id")
        action = (item.get("action") or "").strip().upper()
        row = {"claim_id": claim_id, "action": action}

        try:
            if not claim_id:
                raise ValueError("claim_id is required.")
            if action == "SUBMIT":
                submission = submit_claim_attachments(
                    int(claim_id),
                    channel=item.get("channel"),
                    submission_reference=item.get("submission_reference"),
                    environment=item.get("environment"),
                    allow_retry=item.get("allow_retry", False),
                )
                row.update(
                    {
                        "success": True,
                        "submission_id": submission.id,
                        "status": submission.status,
                    }
                )
            elif action == "CONFIRM":
                submission = confirm_attachment_submission(
                    int(claim_id),
                    submission_id=item.get("submission_id"),
                    submission_reference=item.get("submission_reference"),
                )
                row.update(
                    {
                        "success": True,
                        "submission_id": submission.id,
                        "status": submission.status,
                    }
                )
            elif action == "FAIL":
                submission = fail_attachment_submission(
                    int(claim_id),
                    submission_id=item.get("submission_id"),
                    notes=item.get("notes"),
                )
                row.update(
                    {
                        "success": True,
                        "submission_id": submission.id,
                        "status": submission.status,
                    }
                )
            else:
                raise ValueError(
                    "action must be SUBMIT, CONFIRM, or FAIL."
                )
            success_count += 1
        except Exception as exc:
            error_count += 1
            row.update({"success": False, "error": str(exc)[:500]})
        results.append(row)

    return {
        "total": len(items),
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
    }
