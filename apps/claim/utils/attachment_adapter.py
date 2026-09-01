"""Production attachment adapter — portal + HCPF MFT channel."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

from apps.claim.choices import AttachmentRoute, AttachmentSubmissionStatus
from apps.claim.models import ClaimDocument
from apps.edi.choices import SFTPDirectoryPurpose
from apps.edi.models import SFTPDirectory
from apps.edi.utils.sftp_client import upload_bytes_via_sftp

logger = logging.getLogger(__name__)

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class AttachmentAdapterResult:
    status: str
    submission_reference: str | None = None
    remote_path: str | None = None
    notes: str | None = None


class BaseAttachmentAdapter:
    channel: str

    def transmit(self, claim, documents, **kwargs) -> AttachmentAdapterResult:
        raise NotImplementedError


def _is_production_context(environment: str | None) -> bool:
    env = (environment or "").strip().upper()
    if env == "PRODUCTION":
        return True
    return bool(getattr(settings, "ATTACHMENT_PRODUCTION_MODE", False))


def _sanitize_segment(value: str) -> str:
    return _SAFE_SEGMENT_RE.sub("_", (value or "").strip()) or "file"


def _build_remote_filename(template: str, claim, doc, stamp: str, filename: str) -> str:
    claim_ref = _sanitize_segment(claim.claim_number or f"claim-{claim.id}")
    doc_type = _sanitize_segment(doc.document_type or "DOC")
    safe_name = _sanitize_segment(filename)
    rendered = (
        template.replace("{claim_number}", claim_ref)
        .replace("{claim_id}", str(claim.id))
        .replace("{document_type}", doc_type)
        .replace("{filename}", safe_name)
        .replace("{stamp}", stamp)
    )
    return rendered.replace("\\", "/").lstrip("/")


class PortalAttachmentAdapter(BaseAttachmentAdapter):
    """Manual Provider Web Portal workflow — queue until staff confirms."""

    channel = AttachmentRoute.HCPF_PORTAL

    def transmit(self, claim, documents, **kwargs) -> AttachmentAdapterResult:
        submission_reference = kwargs.get("submission_reference")
        if submission_reference:
            return AttachmentAdapterResult(
                status=AttachmentSubmissionStatus.SUBMITTED,
                submission_reference=submission_reference,
                notes="Recorded portal submission reference.",
            )
        return AttachmentAdapterResult(
            status=AttachmentSubmissionStatus.QUEUED,
            notes=(
                "Submit signed documents via HCPF Provider Web Portal "
                "and record submission_reference when confirmed."
            ),
        )


class MftAttachmentAdapter(BaseAttachmentAdapter):
    """Upload document blobs to configured SFTP OUTBOUND_ATTACHMENT directory."""

    channel = AttachmentRoute.HCPF_APPROVED_CHANNEL

    def _resolve_directory(self, environment: str, production: bool):
        directory = (
            SFTPDirectory.objects.filter(
                purpose=SFTPDirectoryPurpose.OUTBOUND_ATTACHMENT,
                is_active=True,
                credentials__environment=environment,
                credentials__is_active=True,
            )
            .select_related("credentials")
            .order_by("-id")
            .first()
        )
        if directory is not None:
            return directory

        if production:
            raise ValueError(
                "Production attachment upload requires an active "
                "OUTBOUND_ATTACHMENT SFTP directory "
                f"(environment={environment})."
            )

        return (
            SFTPDirectory.objects.filter(
                purpose=SFTPDirectoryPurpose.GENERAL,
                is_active=True,
                credentials__environment=environment,
                credentials__is_active=True,
            )
            .select_related("credentials")
            .order_by("-id")
            .first()
        )

    def transmit(self, claim, documents, **kwargs) -> AttachmentAdapterResult:
        if not getattr(settings, "ATTACHMENT_MFT_ENABLED", False):
            return AttachmentAdapterResult(
                status=AttachmentSubmissionStatus.QUEUED,
                notes=(
                    "MFT attachment adapter is disabled "
                    "(ATTACHMENT_MFT_ENABLED=false). "
                    "Use portal workflow or enable MFT."
                ),
            )

        environment = kwargs.get("environment") or getattr(
            settings, "ATTACHMENT_MFT_ENVIRONMENT", "TEST"
        )
        environment = str(environment).strip().upper()
        production = _is_production_context(environment)

        directory = self._resolve_directory(environment, production)
        if directory is None or directory.credentials is None:
            raise ValueError(
                "No active SFTP directory configured for attachment upload "
                f"(environment={environment})."
            )

        credentials = directory.credentials
        if not credentials.is_active:
            raise ValueError("SFTP credentials for attachment upload are inactive.")

        template = getattr(
            settings,
            "ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE",
            "{claim_number}/{document_type}/{filename}",
        )
        claim_ref = claim.claim_number or f"claim-{claim.id}"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        uploaded_paths = []

        for doc in documents:
            if not doc.blob_ref:
                raise ValueError(
                    f"Document {doc.document_type} has no stored file (blob_ref missing)."
                )
            from apps.claim.utils.document_storage import download_claim_document_bytes

            data, _content_type = download_claim_document_bytes(doc.blob_ref)
            filename = doc.file_name or f"{doc.document_type}.pdf"
            remote_name = _build_remote_filename(
                template, claim, doc, stamp, filename
            )
            remote = upload_bytes_via_sftp(
                credentials=credentials,
                remote_dir=directory.sending_path,
                filename=remote_name,
                data=data,
            )
            uploaded_paths.append(remote)

        remote_path = (
            uploaded_paths[0]
            if len(uploaded_paths) == 1
            else ",".join(uploaded_paths)
        )
        reference = f"MFT-{claim_ref}-{stamp}"
        mode_note = "production" if production else "test"
        return AttachmentAdapterResult(
            status=AttachmentSubmissionStatus.SUBMITTED,
            submission_reference=reference,
            remote_path=remote_path,
            notes=(
                f"Uploaded {len(uploaded_paths)} file(s) via SFTP "
                f"({mode_note}, dir={directory.name or directory.id})."
            ),
        )


def get_attachment_adapter(channel: str | None = None) -> BaseAttachmentAdapter:
    route = (channel or "").strip().upper()
    if not route:
        if getattr(settings, "ATTACHMENT_PRODUCTION_MODE", False):
            route = getattr(
                settings,
                "ATTACHMENT_PRODUCTION_DEFAULT_CHANNEL",
                AttachmentRoute.HCPF_APPROVED_CHANNEL,
            )
        else:
            route = getattr(
                settings, "ATTACHMENT_ADAPTER_DEFAULT", AttachmentRoute.HCPF_PORTAL
            )

    if route == AttachmentRoute.HCPF_APPROVED_CHANNEL:
        return MftAttachmentAdapter()
    if route == AttachmentRoute.HCPF_PORTAL:
        return PortalAttachmentAdapter()

    raise ValueError(f"Unsupported attachment channel: {route}")


def load_transmit_documents(claim_id: int) -> list[ClaimDocument]:
    return list(
        ClaimDocument.objects.filter(
            claim_id=claim_id,
            is_active=True,
            blob_ref__isnull=False,
        ).exclude(blob_ref="")
    )
