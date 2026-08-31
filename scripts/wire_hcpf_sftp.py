"""One-off: wire HCPF Edifecs MFT SFTP into DB and smoke-test list."""

import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redartdigital.settings.docker")

import django

django.setup()

from apps.edi.choices import SFTPAuthType, SFTPDirectoryPurpose
from apps.edi.models import SFTPCredentials, SFTPDirectory
from apps.edi.utils.sftp_client import open_sftp
from apps.trading_partner.models import TradingPartner


def main():
    pem_path = Path("/tmp/privateKey.pem")
    if not pem_path.exists():
        raise SystemExit("Missing /tmp/privateKey.pem inside container")
    pem = pem_path.read_text(encoding="utf-8")
    if "BEGIN" not in pem:
        raise SystemExit("privateKey.pem does not look like a PEM key")

    partner = (
        TradingPartner.objects.filter(sender_id="89513013", is_active=True)
        .order_by("-id")
        .first()
    )
    print("partner_id", getattr(partner, "id", None))

    cred, created = SFTPCredentials.objects.update_or_create(
        name="HCPF-MFT-EDIFECS",
        environment="TEST",
        defaults={
            "trading_partner": partner,
            "host": "sftp.mft.edifecsfedcloud.com",
            "port": 22,
            "username": "mft_task_01fce47a-0498-4fb4-wt4m",
            "auth_type": SFTPAuthType.PRIVATE_KEY,
            "password": None,
            "private_key_pem": pem,
            "private_key_passphrase": None,
            "timeout_seconds": 45,
            "notes": "HCPF Edifecs MFT (Task 5). Key-only auth.",
            "is_active": True,
        },
    )
    print("credentials_id", cred.id, "created" if created else "updated")

    send = "Outgoing/edifecs.stco.hosted/toedifecs"
    recv = "Incoming/edifecs.stco.hosted/fromedifecs"

    outbound, _ = SFTPDirectory.objects.update_or_create(
        credentials=cred,
        purpose=SFTPDirectoryPurpose.OUTBOUND_837P,
        sending_path=send,
        receiving_path=recv,
        defaults={"name": "HCPF 837P send / 999 recv", "is_active": True},
    )
    inbound, _ = SFTPDirectory.objects.update_or_create(
        credentials=cred,
        purpose=SFTPDirectoryPurpose.INBOUND_999,
        sending_path=send,
        receiving_path=recv,
        defaults={"name": "HCPF Import 999 recv", "is_active": True},
    )
    print("outbound_dir_id", outbound.id, "inbound_dir_id", inbound.id)

    print("--- listing remote ---")
    with open_sftp(cred) as sftp:
        for name in sorted(sftp.listdir(".")):
            print("root:", name)
        for candidate in (
            "Outgoing",
            "Incoming",
            "outgoing",
            "incoming",
            "ToEdifecs",
            "FromEdifecs",
        ):
            try:
                entries = sftp.listdir(candidate)
                print(f"dir {candidate}:", entries[:40])
            except Exception as exc:
                print(f"dir {candidate}: ERR {type(exc).__name__}")
    print("SFTP_OK")


if __name__ == "__main__":
    main()
