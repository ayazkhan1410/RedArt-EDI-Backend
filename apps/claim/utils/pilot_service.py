"""Long-distance pilot orchestration for RedArt → EDI API integration."""

from __future__ import annotations

import logging

from django.db import transaction

from apps.claim.choices import BatchStatus, ClaimStatus
from apps.claim.models import Claim, SubmissionBatch
from apps.claim.utils.attachment_service import submit_claim_attachments
from apps.claim.utils.service import add_claim_to_batch, assert_claim_ready_for_batch
from apps.edi.utils.handler import Generate837PHandler
from apps.edi.utils.upload import queue_edi_file_upload
from apps.trading_partner.models import TradingPartner

logger = logging.getLogger(__name__)


@transaction.atomic
def run_long_distance_pilot(
    *,
    claim_id: int,
    trading_partner_id: int,
    batch_number: str | None = None,
    environment: str | None = None,
    submit_attachments: bool = True,
    attachment_channel: str | None = None,
    attachment_reference: str | None = None,
    queue_upload: bool = False,
    upload_async: bool = True,
):
    """
    Step-8 orchestration: attachments → batch → 837P → optional SFTP upload.
    Returns a step timeline for RedArt backend polling.
    """
    claim = (
        Claim.objects.select_for_update()
        .filter(pk=claim_id, is_active=True)
        .first()
    )
    if claim is None:
        raise ValueError("Claim not found or inactive.")
    if not claim.attachment_required:
        raise ValueError("Claim is not a long-distance / attachment-required claim.")

    partner = TradingPartner.objects.filter(pk=trading_partner_id, is_active=True).first()
    if partner is None:
        raise ValueError("Trading partner not found or inactive.")

    env = (environment or partner.environment or "TEST").strip().upper()
    steps = []

    assert_claim_ready_for_batch(claim)
    claim.refresh_from_db()
    steps.append(
        {
            "step": "documents_ready",
            "status": "ok",
            "claim_status": claim.status,
        }
    )

    attachment_submission_id = None
    if submit_attachments:
        submission = submit_claim_attachments(
            claim.id,
            channel=attachment_channel,
            submission_reference=attachment_reference,
            environment=env,
        )
        attachment_submission_id = submission.id
        claim.refresh_from_db()
        steps.append(
            {
                "step": "attachments_submitted",
                "status": submission.status,
                "attachment_submission_id": submission.id,
                "submission_reference": submission.submission_reference,
            }
        )

    batch = SubmissionBatch.objects.create(
        batch_number=batch_number,
        trading_partner=partner,
        environment=env,
        status=BatchStatus.READY,
        is_active=True,
    )
    batch_claim = add_claim_to_batch(
        batch_id=batch.id,
        claim_id=claim.id,
    )
    claim.refresh_from_db()
    steps.append(
        {
            "step": "batch_claim_added",
            "status": "ok",
            "batch_id": batch.id,
            "batch_claim_id": batch_claim.id,
            "st02": batch_claim.st02,
            "claim_status": claim.status,
        }
    )

    handler = Generate837PHandler(batch.id)
    edi_file, _, _ = handler.generate()
    claim.refresh_from_db()
    steps.append(
        {
            "step": "837p_generated",
            "status": "ok",
            "edi_file_id": edi_file.id,
            "filename": edi_file.filename,
            "claim_status": claim.status,
        }
    )

    upload_info = None
    if queue_upload:
        edi_file, attempt, sftp_log, s3_log = queue_edi_file_upload(
            edi_file.id,
            async_mode=upload_async,
        )
        upload_info = {
            "attempt": attempt,
            "sftp_transfer_log_id": sftp_log.id,
            "s3_transfer_log_id": s3_log.id,
            "async": upload_async,
        }
        steps.append(
            {
                "step": "837p_upload_queued",
                "status": edi_file.status,
                "edi_file_id": edi_file.id,
                **upload_info,
            }
        )

    claim.refresh_from_db()
    return {
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "claim_status": claim.status,
        "batch_id": batch.id,
        "batch_number": batch.batch_number,
        "st02": batch_claim.st02,
        "edi_file_id": edi_file.id,
        "attachment_submission_id": attachment_submission_id,
        "next_actions": [
            "POST /api/v1/edi-acknowledgements/import-999/ after HCPF 999",
            "POST /api/v1/edi-validation-reports/import/ for Edifecs XML",
            "POST /api/v1/edi-acknowledgements/import-277/ when 277CA arrives",
        ],
        "steps": steps,
    }
