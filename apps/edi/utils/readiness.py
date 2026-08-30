"""Pre-flight checks before 837P generation."""

from apps.claim.models import BatchClaim, SubmissionBatch
from apps.claim.utils.service import assert_claim_ready_for_batch
from apps.edi.utils.envelope import get_edi_envelope_config


def assert_batch_ready_for_837p_generation(batch):
    """
    Raise ValueError if a batch cannot safely feed an 837P generator.
    - trading partner required (ISA/GS ids)
    - at least one active batch claim
    - each claim docs-complete / READY path
    - patient demographics for NM1/N3/N4/DMG
    - diagnosis, POS, and at least one service line
    """
    if batch is None or not getattr(batch, "is_active", False):
        raise ValueError("Batch not found or inactive.")

    if not batch.trading_partner_id:
        raise ValueError(
            "Batch trading_partner is required for 837P envelope sender/receiver."
        )
    partner = batch.trading_partner
    if not partner.is_active:
        raise ValueError("Trading partner is inactive.")
    if not partner.sender_id or not partner.receiver_id:
        raise ValueError(
            "Trading partner sender_id and receiver_id are required for ISA/GS."
        )

    # Envelope constants must resolve (settings-backed).
    get_edi_envelope_config(batch.environment or partner.environment)

    rows = (
        BatchClaim.objects.with_relations()
        .filter(batch_id=batch.id, is_active=True)
        .select_related(
            "claim",
            "claim__trip",
            "claim__trip__patient",
            "claim__trip__provider",
        )
    )
    if not rows.exists():
        raise ValueError("Batch has no active claims; cannot generate 837P.")

    for row in rows:
        claim = row.claim
        if claim is None or not claim.is_active:
            raise ValueError(f"BatchClaim {row.id} has no active claim.")

        assert_claim_ready_for_batch(claim)

        if not claim.diagnosis_code:
            raise ValueError(
                f"Claim {claim.claim_number or claim.id} is missing diagnosis_code."
            )
        if not claim.place_of_service:
            raise ValueError(
                f"Claim {claim.claim_number or claim.id} is missing place_of_service."
            )

        trip = claim.trip
        if trip is None or not trip.patient_id:
            raise ValueError(
                f"Claim {claim.claim_number or claim.id} is missing trip/patient."
            )
        patient = trip.patient
        if not patient.has_837p_demographics():
            raise ValueError(
                f"Patient {patient.id} is missing 837P demographics "
                "(gender, address_line_1, city, state, zip)."
            )
        if trip.provider_id is None:
            raise ValueError(
                f"Claim {claim.claim_number or claim.id} is missing billing provider."
            )
        provider = trip.provider
        if not provider.npi:
            raise ValueError(
                f"Provider {provider.id} is missing NPI required for 837P."
            )

        if not claim.service_lines.filter(is_active=True).exists():
            raise ValueError(
                f"Claim {claim.claim_number or claim.id} has no active service lines."
            )

    return True


def load_batch_for_837p(batch_id):
    batch = (
        SubmissionBatch.objects.select_related("trading_partner")
        .filter(pk=batch_id, is_active=True)
        .first()
    )
    if batch is None:
        raise ValueError("Batch not found or inactive.")
    assert_batch_ready_for_837p_generation(batch)
    return batch
