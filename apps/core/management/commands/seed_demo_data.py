"""
Seed data matching the client-approved 837P sample (RedArt / CO Medicaid).

Usage:
  python manage.py seed_demo_data --flush-all
  python manage.py seed_demo_data --flush-demo   # legacy DEMO-* keys only

After --flush-all, generate-837p for batch REDART-SAMPLE-837P should emit
the same segment shape as the approved file (dates/control #s will differ).
"""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.claim.choices import BatchStatus, ClaimStatus
from apps.claim.models import (
    AttachmentSubmission,
    BatchClaim,
    Claim,
    ClaimDocument,
    SubmissionBatch,
)
from apps.claim.utils.service import add_claim_to_batch, refresh_batch_totals
from apps.claim_service_line.models import ClaimServiceLine
from apps.edi.choices import SFTPAuthType, SFTPDirectoryPurpose
from apps.edi.models import (
    EDI999Import,
    EDIAcknowledgement,
    EDIControlNumber,
    EDIFile,
    EDIFileTransferLog,
    SFTPCredentials,
    SFTPDirectory,
)
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile
from apps.trading_partner.models import TradingPartner

# All values below are clearly synthetic / non-real.
# No company, person, address, NPI, or credential belonging to any real entity
# should ever appear in source code — not even as a "sample".
SAMPLE_BATCH_NUMBER = "SAMPLE-BATCH-0001"
SAMPLE_CLAIM_NUMBER = "SAMPLECLAIM0001"
SAMPLE_MEMBER_ID = "SMPLMEMBER001"     # clearly fake Medicaid member ID
SAMPLE_NPI = "1999999999"             # 10-digit test NPI (not a real NPI)
SAMPLE_SENDER = "SMPLSENDER1"         # clearly fake sender/TPID


class Command(BaseCommand):
    help = (
        "Wipe domain data (optional) and seed the client-approved RedArt 837P sample."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush-all",
            action="store_true",
            help="Delete all rows from app domain models before seeding.",
        )
        parser.add_argument(
            "--flush-demo",
            action="store_true",
            help="Delete legacy DEMO-* seeded rows before insert.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush_all"]:
            self._flush_all()
            self.stdout.write(self.style.WARNING("Flushed all domain model rows."))
        elif options["flush_demo"]:
            self._flush_demo()
            self.stdout.write(self.style.WARNING("Flushed previous DEMO-* rows."))

        self._seed_long_distance_rules()
        partner = self._seed_trading_partner()
        provider = self._seed_provider()
        patient = self._seed_patient()
        trip = self._seed_trip(patient, provider)
        claim = self._seed_claim(trip)
        lines = self._seed_service_lines(claim)
        batch, batch_claim = self._seed_batch(partner, claim)
        env_cred, env_dirs = self._seed_sftp_from_env([partner])

        self.stdout.write(self.style.SUCCESS("Approved-sample seed complete:"))
        self.stdout.write(f"  TradingPartner id={partner.id} sender={partner.sender_id}")
        self.stdout.write(f"  Provider NPI={provider.npi}")
        self.stdout.write(f"  Patient medicaid={patient.medicaid_member_id}")
        self.stdout.write(f"  NemtTrip id={trip.id} DOS={trip.service_date}")
        self.stdout.write(f"  Claim {claim.claim_number} total={claim.total_charge}")
        self.stdout.write(f"  Service lines: {len(lines)}")
        self.stdout.write(
            f"  Batch {batch.batch_number} id={batch.id} st02={batch_claim.st02}"
        )
        if env_cred:
            self.stdout.write(f"  SFTPCredentials: {env_cred.name} (+{len(env_dirs)} dirs)")
        else:
            self.stdout.write("  SFTP env seed skipped (set SFTP_SEED_*).")
        self.stdout.write(
            self.style.SUCCESS(
                f"Next: POST /api/v1/edi-files/generate-837p/ with batch_id={batch.id}"
            )
        )

    def _flush_all(self):
        """Hard-delete all EDI / claim / trip domain rows (FK-safe order)."""
        EDI999Import.objects.all().delete()
        EDIFileTransferLog.objects.all().delete()
        EDIAcknowledgement.objects.all().delete()
        EDIFile.objects.all().delete()
        EDIControlNumber.objects.all().delete()
        BatchClaim.objects.all().delete()
        SubmissionBatch.objects.all().delete()
        AttachmentSubmission.objects.all().delete()
        ClaimDocument.objects.all().delete()
        ClaimServiceLine.objects.all().delete()
        Claim.objects.all().delete()
        NemtTrip.objects.all().delete()
        Patient.objects.all().delete()
        ProviderBillingProfile.objects.all().delete()
        SFTPDirectory.objects.all().delete()
        SFTPCredentials.objects.all().delete()
        TradingPartner.objects.all().delete()
        LongDistanceRule.objects.all().delete()

    def _flush_demo(self):
        SFTPDirectory.objects.filter(
            credentials__name__startswith="DEMO-SFTP-"
        ).delete()
        SFTPCredentials.objects.filter(name__startswith="DEMO-SFTP-").delete()
        seed_name = getattr(settings, "SFTP_SEED_NAME", "SEED-SFTP-CLOUD")
        SFTPDirectory.objects.filter(credentials__name=seed_name).delete()
        SFTPCredentials.objects.filter(name=seed_name).delete()
        EDI999Import.objects.filter(
            batch__batch_number__startswith="DEMO-"
        ).delete()
        EDIAcknowledgement.objects.filter(
            batch__batch_number__startswith="DEMO-"
        ).delete()
        EDIFileTransferLog.objects.filter(
            edi_file__batch__batch_number__startswith="DEMO-"
        ).delete()
        EDIFile.objects.filter(batch__batch_number__startswith="DEMO-").delete()
        EDIControlNumber.objects.filter(
            batch__batch_number__startswith="DEMO-"
        ).delete()
        BatchClaim.objects.filter(
            batch__batch_number__startswith="DEMO-"
        ).delete()
        SubmissionBatch.objects.filter(batch_number__startswith="DEMO-").delete()
        AttachmentSubmission.objects.filter(
            claim__claim_number__startswith="DEMO-"
        ).delete()
        ClaimDocument.objects.filter(
            claim__claim_number__startswith="DEMO-"
        ).delete()
        ClaimServiceLine.objects.filter(
            claim__claim_number__startswith="DEMO-"
        ).delete()
        Claim.objects.filter(claim_number__startswith="DEMO-").delete()
        NemtTrip.objects.filter(pickup__startswith="DEMO-").delete()
        Patient.objects.filter(medicaid_member_id__startswith="DEMO-").delete()
        ProviderBillingProfile.objects.filter(npi__startswith="17500").delete()
        TradingPartner.objects.filter(sender_id__startswith="DEMO-TP").delete()

    def _seed_long_distance_rules(self):
        LongDistanceRule.objects.update_or_create(
            county_type="STANDARD",
            defaults={
                "review_threshold": 52,
                "verification_threshold": 25,
                "is_active": True,
            },
        )
        LongDistanceRule.objects.update_or_create(
            county_type="DESIGNATED_RURAL",
            defaults={
                "review_threshold": 125,
                "verification_threshold": 25,
                "is_active": True,
            },
        )

    def _seed_trading_partner(self):
        obj, _ = TradingPartner.objects.update_or_create(
            sender_id=SAMPLE_SENDER,
            receiver_id="COMEDASSISTPROG",
            environment="TEST",
            defaults={
                "name": "SAMPLE TRANSPORT LLC",
                "contact_name": "BILLING CONTACT",
                "contact_phone": "0000000000",
                "is_active": True,
            },
        )
        return obj

    def _seed_provider(self):
        obj, _ = ProviderBillingProfile.objects.update_or_create(
            npi=SAMPLE_NPI,
            defaults={
                "legal_name": "SAMPLE TRANSPORT LLC",
                "billing_name": "SAMPLE TRANSPORT LLC",
                "taxonomy_code": "343900000X",
                "tax_id": "000000000",  # clearly fake EIN for test only
                "location_id": SAMPLE_NPI,
                "address_line_1": "100 SAMPLE ST",
                "city": "DENVER",
                "state": "CO",
                "zip": "80000",
                "country": "US",
                "phone": "0000000000",
                "email": "billing@sample.example",
                "is_active": True,
            },
        )
        return obj

    def _seed_patient(self):
        obj, _ = Patient.objects.update_or_create(
            medicaid_member_id=SAMPLE_MEMBER_ID,
            defaults={
                "first_name": "SAMPLE",
                "last_name": "PATIENT",
                "date_of_birth": date(1970, 1, 1),
                "gender": "F",
                "county": "Denver",
                "address_line_1": "100 SAMPLE ST",
                "city": "DENVER",
                "state": "CO",
                "zip": "80000",
                "phone": "0000000000",
                "email": "sample.patient@example.com",
                "is_active": True,
            },
        )
        return obj

    def _seed_trip(self, patient, provider):
        obj, _ = NemtTrip.objects.update_or_create(
            patient=patient,
            provider=provider,
            service_date=date(2026, 8, 5),
            pickup="100 TEST STREET, PUEBLO CO",
            defaults={
                "dropoff": "Clinic, Pueblo CO",
                "one_way_miles": Decimal("8.00"),
                "mileage_units": 1,
                "driver_first_name": "CHRIS",
                "driver_last_name": "TESTDRIVER",
                "charge": Decimal("14.90"),
                "is_active": True,
            },
        )
        return obj

    def _seed_claim(self, trip):
        claim, _ = Claim.objects.update_or_create(
            claim_number=SAMPLE_CLAIM_NUMBER,
            defaults={
                "external_id": "SAMPLE-TRIP-0001",
                "trip": trip,
                "diagnosis_code": "R69",
                "place_of_service": "03",
                "total_charge": Decimal("14.90"),
                "status": ClaimStatus.READY_FOR_837P,
                "attachment_required": False,
                "is_active": True,
            },
        )
        return claim

    def _seed_service_lines(self, claim):
        dos = date(2026, 8, 5)
        specs = [
            ("A0120", Decimal("12.15")),
            ("S0215", Decimal("2.75")),
        ]
        lines = []
        for code, charge in specs:
            line, _ = ClaimServiceLine.objects.update_or_create(
                claim=claim,
                procedure_code=code,
                defaults={
                    "from_date": dos,
                    "to_date": dos,
                    "units": 1,
                    "mileage": Decimal("0.00") if code == "S0215" else Decimal("8.00"),
                    "charge": charge,
                    "is_active": True,
                },
            )
            lines.append(line)
        return lines

    def _seed_batch(self, partner, claim):
        batch, _ = SubmissionBatch.objects.update_or_create(
            batch_number=SAMPLE_BATCH_NUMBER,
            defaults={
                "trading_partner": partner,
                "environment": "TEST",
                "status": BatchStatus.READY,
                "is_active": True,
            },
        )
        existing = BatchClaim.objects.filter(
            batch=batch, claim=claim, is_active=True
        ).first()
        if existing is None:
            add_claim_to_batch(
                batch_id=batch.id, claim_id=claim.id, st02="0001"
            )
            existing = BatchClaim.objects.get(
                batch=batch, claim=claim, is_active=True
            )
        else:
            existing.st02 = "0001"
            existing.save(update_fields=["st02", "updated_at"])
        refresh_batch_totals(batch)
        batch.refresh_from_db()
        return batch, existing

    def _seed_sftp_from_env(self, partners):
        host = (getattr(settings, "SFTP_SEED_HOST", "") or "").strip()
        username = (getattr(settings, "SFTP_SEED_USERNAME", "") or "").strip()
        password = (getattr(settings, "SFTP_SEED_PASSWORD", "") or "").strip()
        if not host or not username or not password:
            return None, []

        name = getattr(settings, "SFTP_SEED_NAME", "SEED-SFTP-CLOUD") or "SEED-SFTP-CLOUD"
        port = int(getattr(settings, "SFTP_SEED_PORT", 22) or 22)
        send_path = getattr(settings, "SFTP_SEED_SEND_PATH", "/send") or "/send"
        recv_path = getattr(settings, "SFTP_SEED_RECV_PATH", "/recv") or "/recv"
        partner = partners[0] if partners else None

        cred, _ = SFTPCredentials.objects.update_or_create(
            name=name,
            environment="TEST",
            defaults={
                "trading_partner": partner,
                "host": host,
                "port": port,
                "username": username,
                "auth_type": SFTPAuthType.PASSWORD,
                "password": password,
                "timeout_seconds": 30,
                "notes": "Seeded from SFTP_SEED_* env (local test).",
                "is_active": True,
            },
        )
        dirs = []
        outbound, _ = SFTPDirectory.objects.update_or_create(
            credentials=cred,
            purpose=SFTPDirectoryPurpose.OUTBOUND_837P,
            sending_path=send_path,
            receiving_path=recv_path,
            defaults={
                "name": f"{name} send/recv",
                "is_active": True,
            },
        )
        dirs.append(outbound)
        inbound, _ = SFTPDirectory.objects.update_or_create(
            credentials=cred,
            purpose=SFTPDirectoryPurpose.INBOUND_999,
            sending_path=send_path,
            receiving_path=recv_path,
            defaults={
                "name": f"{name} Import 999 recv",
                "is_active": True,
            },
        )
        dirs.append(inbound)
        self.stdout.write(
            self.style.SUCCESS(
                f"  SFTP env seed: {name} → {host} ({send_path}, {recv_path})"
            )
        )
        return cred, dirs
