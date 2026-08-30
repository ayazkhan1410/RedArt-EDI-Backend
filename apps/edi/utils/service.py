"""EDI control-number allocation and file record helpers."""

from django.db import transaction
from django.utils import timezone

from apps.claim.choices import BatchStatus
from apps.claim.models import SubmissionBatch
from apps.edi.choices import EDIFileStatus, TransactionType
from apps.edi.models import EDIControlNumber, EDIFile


def _digits_only(value):
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits or None


def next_isa13(environment):
    """Next 9-digit ISA13 for the environment (starts at 000000001)."""
    rows = (
        EDIControlNumber.objects.filter(
            environment=environment,
            is_active=True,
        )
        .exclude(isa13__isnull=True)
        .exclude(isa13="")
        .values_list("isa13", flat=True)
    )
    max_n = 0
    for value in rows:
        digits = _digits_only(value)
        if digits:
            max_n = max(max_n, int(digits))
    return f"{max_n + 1:09d}"


def next_gs06(environment):
    """Next GS06 for the environment (integer sequence as string)."""
    rows = (
        EDIControlNumber.objects.filter(
            environment=environment,
            is_active=True,
        )
        .exclude(gs06__isnull=True)
        .exclude(gs06="")
        .values_list("gs06", flat=True)
    )
    max_n = 0
    for value in rows:
        digits = _digits_only(value)
        if digits:
            max_n = max(max_n, int(digits))
    return str(max_n + 1)


def build_colorado_837p_filename(
    *,
    sender_id,
    generated_at=None,
    part=1,
    of_parts=1,
):
    """
    Colorado-style outbound name:
    {sender}-837P-{YYYYMMDDHHMMSSmmm}-{part}of{of_parts}.txt
    """
    when = generated_at or timezone.now()
    if timezone.is_naive(when):
        stamp = when.strftime("%Y%m%d%H%M%S") + f"{when.microsecond // 1000:03d}"
    else:
        local = timezone.localtime(when)
        stamp = local.strftime("%Y%m%d%H%M%S") + f"{local.microsecond // 1000:03d}"
    sender = (sender_id or "UNKNOWN").strip() or "UNKNOWN"
    return f"{sender}-837P-{stamp}-{part}of{of_parts}.txt"


@transaction.atomic
def allocate_control_numbers(
    *,
    batch_id,
    isa13=None,
    gs06=None,
    environment=None,
):
    """
    Create (or return existing active) EDIControlNumber for a batch.
    Allocates next ISA13/GS06 per environment when not provided.
    """
    batch = (
        SubmissionBatch.objects.select_for_update(of=("self",))
        .select_related("trading_partner")
        .filter(pk=batch_id, is_active=True)
        .first()
    )
    if batch is None:
        raise ValueError("Batch not found or inactive.")

    existing = (
        EDIControlNumber.objects.select_for_update(of=("self",))
        .filter(batch_id=batch.id, is_active=True)
        .first()
    )
    if existing is not None:
        return existing, False

    env = (environment or batch.environment or "TEST").strip().upper()
    isa = _digits_only(isa13) or next_isa13(env)
    gs = _digits_only(gs06) or next_gs06(env)

    if len(isa) > 9:
        raise ValueError("isa13 must be at most 9 digits.")
    isa = isa.zfill(9)

    row = EDIControlNumber.objects.create(
        batch=batch,
        environment=env,
        isa13=isa,
        gs06=gs,
        is_active=True,
    )
    return row, True


@transaction.atomic
def create_edi_file_for_batch(
    *,
    batch_id,
    transaction_type=TransactionType.X837P,
    filename=None,
    file_hash=None,
    path_or_blob_ref=None,
    status=EDIFileStatus.GENERATED,
    uploaded_at=None,
    allocate_controls=True,
):
    """
    Create an EDIFile row for a batch.
    Optionally allocates control numbers first.
    Does not generate X12 payload yet — stores transport metadata only.
    """
    batch = (
        SubmissionBatch.objects.select_for_update(of=("self",))
        .select_related("trading_partner")
        .filter(pk=batch_id, is_active=True)
        .first()
    )
    if batch is None:
        raise ValueError("Batch not found or inactive.")

    if batch.claim_count < 1:
        raise ValueError("Batch has no claims; cannot create EDI file.")

    control = None
    if allocate_controls:
        control, _ = allocate_control_numbers(batch_id=batch.id)

    txn = (transaction_type or TransactionType.X837P).strip().upper()
    if txn not in TransactionType.values:
        raise ValueError("Invalid transaction_type.")

    if not filename:
        sender = None
        if batch.trading_partner_id:
            sender = batch.trading_partner.sender_id
        filename = build_colorado_837p_filename(sender_id=sender)

    if EDIFile.objects.filter(filename=filename).exists():
        raise ValueError("An EDI file with this filename already exists.")

    status_value = (status or EDIFileStatus.GENERATED).strip().upper()
    if status_value not in EDIFileStatus.values:
        raise ValueError("Invalid EDI file status.")

    if status_value == EDIFileStatus.UPLOADED and uploaded_at is None:
        uploaded_at = timezone.now()

    edi_file = EDIFile.objects.create(
        batch=batch,
        control_number=control,
        transaction_type=txn,
        filename=filename,
        file_hash=file_hash,
        path_or_blob_ref=path_or_blob_ref,
        status=status_value,
        uploaded_at=uploaded_at,
        is_active=True,
    )

    if batch.status in (BatchStatus.DRAFT, BatchStatus.READY, None, ""):
        batch.status = BatchStatus.GENERATED
        batch.save(update_fields=["status", "updated_at"])

    return edi_file


@transaction.atomic
def mark_edi_file_uploaded(edi_file_id, *, path_or_blob_ref=None, file_hash=None):
    edi_file = (
        EDIFile.objects.select_for_update(of=("self",))
        .select_related("batch")
        .filter(pk=edi_file_id, is_active=True)
        .first()
    )
    if edi_file is None:
        raise ValueError("EDI file not found or inactive.")

    edi_file.status = EDIFileStatus.UPLOADED
    edi_file.uploaded_at = timezone.now()
    update_fields = ["status", "uploaded_at", "updated_at"]
    if path_or_blob_ref is not None:
        edi_file.path_or_blob_ref = path_or_blob_ref
        update_fields.append("path_or_blob_ref")
    if file_hash is not None:
        edi_file.file_hash = file_hash
        update_fields.append("file_hash")
    edi_file.save(update_fields=update_fields)

    batch = edi_file.batch
    if batch is not None and batch.status in (
        BatchStatus.READY,
        BatchStatus.GENERATED,
        BatchStatus.DRAFT,
    ):
        batch.status = BatchStatus.SUBMITTED
        batch.save(update_fields=["status", "updated_at"])

    return edi_file
