"""Import / apply HIPAA 835 remittance advice (paid / denied)."""

from __future__ import annotations

import hashlib
import logging

from django.db import transaction
from django.db.models import Q

from apps.claim.choices import ClaimStatus
from apps.claim.models import Claim
from apps.edi.choices import RemittanceClaimOutcome
from apps.edi.models import EDI835ClaimPayment, EDI835Remittance
from apps.edi.utils.x12 import parse_835

logger = logging.getLogger(__name__)

# Outcomes that may update Claim.status.
_APPLY_OUTCOMES = {
    RemittanceClaimOutcome.PAID: ClaimStatus.PAID,
    RemittanceClaimOutcome.DENIED: ClaimStatus.DENIED,
    RemittanceClaimOutcome.UNDER_REVIEW: ClaimStatus.UNDER_REVIEW,
}

# Do not overwrite these with UNDER_REVIEW (weaker signal).
_TERMINAL_PAYMENT = frozenset({ClaimStatus.PAID, ClaimStatus.DENIED})


def content_sha256(raw: str) -> str:
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _find_claim(claim_number: str, *, by_number: dict | None = None):
    number = (claim_number or "").strip()
    if not number:
        return None
    if by_number is not None:
        return by_number.get(number)
    return (
        Claim.objects.filter(is_active=True)
        .filter(Q(claim_number=number) | Q(external_id=number))
        .order_by("-id")
        .first()
    )


def _claim_lookup_map(claim_numbers: list[str]) -> dict[str, Claim]:
    """One query for all CLP claim numbers / external ids."""
    numbers = sorted({(n or "").strip() for n in claim_numbers if (n or "").strip()})
    if not numbers:
        return {}
    claims = list(
        Claim.objects.filter(is_active=True)
        .filter(Q(claim_number__in=numbers) | Q(external_id__in=numbers))
        .order_by("id")
    )
    by_number: dict[str, Claim] = {}
    for claim in claims:
        if claim.claim_number:
            by_number.setdefault(claim.claim_number.strip(), claim)
        if claim.external_id:
            by_number.setdefault(claim.external_id.strip(), claim)
    return by_number


def _should_apply_status(*, claim, new_status: str) -> tuple[bool, str | None]:
    current = (claim.status or "").strip().upper()
    if current == new_status:
        return False, "Claim already has this status."
    if (
        new_status == ClaimStatus.UNDER_REVIEW
        and current in _TERMINAL_PAYMENT
    ):
        return False, f"Refuse UNDER_REVIEW overwrite of terminal status {current}."
    return True, None


@transaction.atomic
def import_835_remittance(
    *,
    content: str,
    raw_file_ref: str | None = None,
    apply_claim_status: bool = True,
):
    """
    Parse 835 X12, persist remittance + CLP lines, optionally set Claim PAID/DENIED.

    Idempotent on content SHA-256: re-import of the same body returns the
    existing remittance without re-applying claim updates.
    """
    if not (content or "").strip():
        raise ValueError("835 content is required.")

    digest = content_sha256(content)
    existing = (
        EDI835Remittance.objects.filter(file_hash=digest, is_active=True)
        .prefetch_related("claim_payments")
        .first()
    )
    if existing is not None:
        applied_ids = list(
            existing.claim_payments.filter(
                status_applied=True, claim_id__isnull=False, is_active=True
            ).values_list("claim_id", flat=True)
        )
        return existing, applied_ids, {"idempotent": True, "parsed": None}

    parsed = parse_835(content)
    remittance = EDI835Remittance.objects.create(
        file_hash=digest,
        raw_file_ref=(raw_file_ref or "").strip() or None,
        isa13=parsed.get("isa13"),
        gs06=parsed.get("gs06"),
        st02=parsed.get("st02"),
        trace_number=parsed.get("trace_number"),
        payment_method=parsed.get("payment_method"),
        total_payment=parsed.get("total_payment"),
        payment_date=parsed.get("payment_date"),
        message=parsed.get("message"),
        claim_line_count=len(parsed["claims"]),
        applied_claim_count=0,
        is_active=True,
    )

    updated_claim_ids: list[int] = []
    applied_count = 0
    by_number = _claim_lookup_map(
        [line.get("claim_number") or "" for line in parsed["claims"]]
    )

    for line in parsed["claims"]:
        claim = _find_claim(line["claim_number"], by_number=by_number)
        outcome = line["outcome"]
        prior_status = claim.status if claim else None
        status_applied = False
        skip_reason = None

        if claim is None:
            skip_reason = "No active claim matched claim_number/external_id."
        elif not apply_claim_status:
            skip_reason = "apply_claim_status=false."
        elif outcome not in _APPLY_OUTCOMES:
            skip_reason = f"Outcome {outcome} does not update claim status."
        else:
            new_status = _APPLY_OUTCOMES[outcome]
            ok, reason = _should_apply_status(claim=claim, new_status=new_status)
            if not ok:
                skip_reason = reason
            else:
                claim.status = new_status
                claim.save(update_fields=["status", "updated_at"])
                status_applied = True
                applied_count += 1
                updated_claim_ids.append(claim.id)

        EDI835ClaimPayment.objects.create(
            remittance=remittance,
            claim=claim,
            claim_number=line["claim_number"][:64],
            clp_status_code=(line.get("clp_status_code") or "")[:8],
            outcome=outcome,
            charge_amount=line.get("charge_amount"),
            payment_amount=line.get("payment_amount"),
            patient_responsibility=line.get("patient_responsibility"),
            payer_claim_control=(line.get("payer_claim_control") or None),
            adjustment_codes=line.get("adjustment_codes"),
            prior_claim_status=prior_status,
            status_applied=status_applied,
            skip_reason=(skip_reason or None),
            is_active=True,
        )

    if applied_count:
        remittance.applied_claim_count = applied_count
        remittance.save(update_fields=["applied_claim_count", "updated_at"])

    logger.info(
        "Imported 835 remittance id=%s lines=%s applied=%s",
        remittance.id,
        remittance.claim_line_count,
        applied_count,
    )
    return remittance, updated_claim_ids, {"idempotent": False, "parsed": parsed}
