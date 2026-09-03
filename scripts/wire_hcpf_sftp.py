"""Wire the HCPF Edifecs production SFTP connection from a Render secret file."""

import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redartdigital.settings.docker")

import django

django.setup()

from apps.edi.choices import SFTPAuthType, SFTPDirectoryPurpose
from apps.edi.models import SFTPCredentials, SFTPDirectory
from apps.edi.utils.sftp_client import open_sftp
from apps.trading_partner.models import TradingPartner

KEY_PATH = Path(
    os.environ.get(
        "HCPF_SFTP_PRIVATE_KEY_PATH",
        "/etc/secrets/edifecs_sftp_private_key.pem",
    )
)
HOST = "sftp.mft.edifecsfedcloud.com"
USERNAME = "mft_task_01fce47a-0498-4fb4-wt4m"
HOST_FINGERPRINT = "SHA256:xhCbKNBog9ztBEubwfUfb1ODz8e/azOlVeaVb77ug8Q"
SEND_PATH = "Outgoing/edifecs.stco.hosted/toedifecs"
RECEIVE_PATH = "Organizational/Incoming/fromedifecs/edifecs.stco.hosted"


def main():
    if not KEY_PATH.exists():
        raise SystemExit(f"Missing Edifecs private key: {KEY_PATH}")

    pem = KEY_PATH.read_text(encoding="utf-8")
    if "BEGIN" not in pem or "PRIVATE KEY" not in pem:
        raise SystemExit("Edifecs secret file does not look like a PEM private key")

    partner = (
        TradingPartner.objects.filter(sender_id="89513013", is_active=True)
        .order_by("-id")
        .first()
    )
    if partner is None:
        raise SystemExit("Active RedArt trading partner 89513013 was not found")

    cred, created = SFTPCredentials.objects.update_or_create(
        name="HCPF-MFT-EDIFECS",
        environment="PRODUCTION",
        defaults={
            "trading_partner": partner,
            "host": HOST,
            "port": 22,
            "username": USERNAME,
            "auth_type": SFTPAuthType.PRIVATE_KEY,
            "password": None,
            "private_key_pem": pem,
            "private_key_passphrase": None,
            "host_fingerprint": HOST_FINGERPRINT,
            "timeout_seconds": 45,
            "notes": "HCPF Edifecs production MFT; key stored as Render secret.",
            "is_active": True,
        },
    )

    purposes = (
        (SFTPDirectoryPurpose.OUTBOUND_837P, "HCPF 837P production send"),
        (SFTPDirectoryPurpose.INBOUND_999, "HCPF 999 production receive"),
        (SFTPDirectoryPurpose.INBOUND_277, "HCPF 277 production receive"),
        (SFTPDirectoryPurpose.INBOUND_835, "HCPF 835 production receive"),
    )
    for purpose, name in purposes:
        SFTPDirectory.objects.update_or_create(
            credentials=cred,
            purpose=purpose,
            defaults={
                "name": name,
                "sending_path": SEND_PATH,
                "receiving_path": RECEIVE_PATH,
                "is_active": True,
            },
        )

    print(
        "HCPF_SFTP_CONFIGURED",
        f"credentials_id={cred.id}",
        "created" if created else "updated",
    )

    if os.environ.get("HCPF_SFTP_SMOKE_TEST", "").lower() == "true":
        with open_sftp(cred) as sftp:
            sftp.listdir(SEND_PATH)
            sftp.listdir(RECEIVE_PATH)
        print("HCPF_SFTP_OK")


if __name__ == "__main__":
    main()
