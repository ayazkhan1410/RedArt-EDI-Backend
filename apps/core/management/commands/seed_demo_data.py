"""
Seed realistic demo rows for local/Docker development.

Usage:
  python manage.py seed_demo_data
  python manage.py seed_demo_data --flush-demo

LongDistanceRule only has two county_type values (unique) — seeds those two.
All other models get at least 5 demo rows (idempotent via known keys).
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.claim.choices import BatchStatus, ClaimStatus, DocumentStatus, DocumentType
from apps.claim.models import BatchClaim, Claim, ClaimDocument, SubmissionBatch
from apps.claim.utils.service import (
    add_claim_to_batch,
    apply_long_distance_flags,
    refresh_batch_totals,
    sync_claim_document_status,
)
from apps.claim_service_line.models import ClaimServiceLine
from apps.edi.choices import EDIFileStatus, SFTPAuthType, SFTPDirectoryPurpose
from apps.edi.models import EDIControlNumber, EDIFile, SFTPCredentials, SFTPDirectory
from apps.edi.utils.service import create_edi_file_for_batch, mark_edi_file_uploaded
from apps.long_distance_rule.models import LongDistanceRule
from apps.nemt_trip.models import NemtTrip
from apps.patient.models import Patient
from apps.provider_billing_profile.models import ProviderBillingProfile
from apps.trading_partner.models import TradingPartner

DEMO_PROVIDER_NPIS = [f"17500{i:05d}" for i in range(1, 6)]


class Command(BaseCommand):
    help = "Seed at least 5 demo rows per domain model (2 for LongDistanceRule)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush-demo",
            action="store_true",
            help="Delete previously seeded demo rows (keys starting with DEMO-) before insert.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush_demo"]:
            self._flush_demo()
            self.stdout.write(self.style.WARNING("Flushed previous DEMO-* rows."))

        self._seed_long_distance_rules()
        partners = self._seed_trading_partners()
        providers = self._seed_providers()
        patients = self._seed_patients()
        trips = self._seed_trips(patients, providers)
        claims = self._seed_claims(trips)
        lines = self._seed_service_lines(claims)
        docs = self._seed_documents(claims)
        batches, batch_claims = self._seed_batches(partners, claims)
        controls, edi_files = self._seed_edi(batches)
        sftp_creds, sftp_dirs = self._seed_sftp(partners)

        self.stdout.write(self.style.SUCCESS("Demo seed complete:"))
        self.stdout.write(f"  TradingPartner:          {len(partners)}")
        self.stdout.write(f"  ProviderBillingProfile:  {len(providers)}")
        self.stdout.write(f"  Patient:                 {len(patients)}")
        self.stdout.write(f"  NemtTrip:                {len(trips)}")
        self.stdout.write(
            f"  LongDistanceRule:        {LongDistanceRule.objects.filter(is_active=True).count()} (unique county types)"
        )
        self.stdout.write(f"  Claim:                   {len(claims)}")
        self.stdout.write(f"  ClaimServiceLine:        {len(lines)}")
        self.stdout.write(f"  ClaimDocument:           {len(docs)}")
        self.stdout.write(f"  SubmissionBatch:         {len(batches)}")
        self.stdout.write(f"  BatchClaim:              {len(batch_claims)}")
        self.stdout.write(f"  EDIControlNumber:        {len(controls)}")
        self.stdout.write(f"  EDIFile:                 {len(edi_files)}")
        self.stdout.write(f"  SFTPCredentials:         {len(sftp_creds)}")
        self.stdout.write(f"  SFTPDirectory:           {len(sftp_dirs)}")

    def _flush_demo(self):
        SFTPDirectory.objects.filter(
            credentials__name__startswith="DEMO-SFTP-"
        ).delete()
        SFTPCredentials.objects.filter(name__startswith="DEMO-SFTP-").delete()
        EDIFile.objects.filter(batch__batch_number__startswith="DEMO-").delete()
        EDIControlNumber.objects.filter(
            batch__batch_number__startswith="DEMO-"
        ).delete()
        BatchClaim.objects.filter(
            batch__batch_number__startswith="DEMO-"
        ).delete()
        SubmissionBatch.objects.filter(batch_number__startswith="DEMO-").delete()
        ClaimDocument.objects.filter(
            claim__claim_number__startswith="DEMO-"
        ).delete()
        ClaimServiceLine.objects.filter(
            claim__claim_number__startswith="DEMO-"
        ).delete()
        Claim.objects.filter(claim_number__startswith="DEMO-").delete()
        NemtTrip.objects.filter(pickup__startswith="DEMO-").delete()
        Patient.objects.filter(medicaid_member_id__startswith="DEMO-").delete()
        ProviderBillingProfile.objects.filter(npi__in=DEMO_PROVIDER_NPIS).delete()
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

    def _seed_trading_partners(self):
        rows = [
            ("Colorado Medicaid TEST", "DEMO-TP001", "COMEDASSISTPROG", "TEST"),
            ("Colorado Medicaid PROD", "DEMO-TP002", "COMEDASSISTPROG", "PRODUCTION"),
            ("Demo Clearinghouse A", "DEMO-TP003", "CLEARHOUSEA", "TEST"),
            ("Demo Clearinghouse B", "DEMO-TP004", "CLEARHOUSEB", "TEST"),
            ("Demo Backup TP", "DEMO-TP005", "BACKUPRECV", "TEST"),
        ]
        partners = []
        for name, sender, receiver, env in rows:
            obj, _ = TradingPartner.objects.update_or_create(
                sender_id=sender,
                receiver_id=receiver,
                environment=env,
                defaults={"name": name, "is_active": True},
            )
            partners.append(obj)
        return partners

    def _seed_providers(self):
        rows = [
            (
                "DEMO Al Shifa Bus Service LLC",
                "Al Shifa Transportation",
                "1750000001",
                "343900000X",
                "9000201481",
            ),
            (
                "DEMO WALLA INVESTMENT LLC",
                "WALLA INVESTMENT LLC",
                "1750000002",
                "343900000X",
                "9000201482",
            ),
            (
                "DEMO Mile High NEMT LLC",
                "Mile High Transport",
                "1750000003",
                "343800000X",
                "9000201483",
            ),
            (
                "DEMO Front Range Rides Inc",
                "Front Range Rides",
                "1750000004",
                "343900000X",
                "9000201484",
            ),
            (
                "DEMO Peak Care Transit LLC",
                "Peak Care Transit",
                "1750000005",
                "343800000X",
                "9000201485",
            ),
        ]
        providers = []
        for legal, billing, npi, taxonomy, location in rows:
            obj, _ = ProviderBillingProfile.objects.update_or_create(
                npi=npi,
                defaults={
                    "legal_name": legal,
                    "billing_name": billing,
                    "taxonomy_code": taxonomy,
                    "location_id": location,
                    "revalidation_date": date(2029, 11, 25),
                    "city": "Denver",
                    "state": "CO",
                    "zip": "80202",
                    "country": "US",
                    "address_line_1": "100 Main St",
                    "phone": "3035550100",
                    "email": f"billing+{npi}@example.com",
                    "is_active": True,
                },
            )
            providers.append(obj)
        return providers

    def _seed_patients(self):
        rows = [
            ("Ali", "Khan", "DEMO-M0001", "Denver", date(1995, 5, 12)),
            ("Sara", "Ahmed", "DEMO-M0002", "Aurora", date(1988, 3, 20)),
            ("Omar", "Hassan", "DEMO-M0003", "Denver", date(2001, 7, 8)),
            ("Fatima", "Noor", "DEMO-M0004", "Lakewood", date(1979, 11, 2)),
            ("Yusuf", "Rahman", "DEMO-M0005", "Denver", date(1992, 1, 15)),
        ]
        patients = []
        for first, last, mid, county, dob in rows:
            obj, _ = Patient.objects.update_or_create(
                medicaid_member_id=mid,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "date_of_birth": dob,
                    "county": county,
                    "email": f"{first.lower()}.{last.lower()}@example.com",
                    "is_active": True,
                },
            )
            patients.append(obj)
        return patients

    def _seed_trips(self, patients, providers):
        # Mix short and long-distance (78 miles) for realistic flags
        miles_list = [
            Decimal("12.00"),
            Decimal("30.00"),
            Decimal("78.00"),
            Decimal("45.00"),
            Decimal("90.00"),
        ]
        trips = []
        base = date(2026, 8, 26)
        for i in range(5):
            miles = miles_list[i]
            units = int(miles)
            pickup = f"DEMO-Pickup-{i + 1}"
            obj, _ = NemtTrip.objects.update_or_create(
                patient=patients[i],
                provider=providers[i],
                service_date=base + timedelta(days=i),
                pickup=pickup,
                defaults={
                    "dropoff": f"DEMO-Clinic-{i + 1}",
                    "one_way_miles": miles,
                    "mileage_units": units,
                    "charge": Decimal(str(50 + i * 25)),
                    "is_active": True,
                },
            )
            trips.append(obj)
        return trips

    def _seed_claims(self, trips):
        claims = []
        for i, trip in enumerate(trips):
            claim_number = f"DEMO-C00{i + 1}"
            claim, created = Claim.objects.get_or_create(
                claim_number=claim_number,
                defaults={
                    "external_id": f"DEMO-TRIP-{1001 + i}",
                    "trip": trip,
                    "diagnosis_code": "R68.89",
                    "place_of_service": "41",
                    "total_charge": trip.charge,
                    "status": ClaimStatus.DRAFT,
                    "is_active": True,
                },
            )
            if created or claim.trip_id != trip.id:
                claim.trip = trip
                claim.external_id = f"DEMO-TRIP-{1001 + i}"
                claim.diagnosis_code = "R68.89"
                claim.place_of_service = "41"
                claim.total_charge = trip.charge
                apply_long_distance_flags(claim, trip)
                claim.save()
            claims.append(claim)
        return claims

    def _seed_service_lines(self, claims):
        lines = []
        for i, claim in enumerate(claims):
            trip = claim.trip
            line, _ = ClaimServiceLine.objects.update_or_create(
                claim=claim,
                procedure_code="A0100",
                defaults={
                    "from_date": trip.service_date if trip else date(2026, 8, 30),
                    "to_date": trip.service_date if trip else date(2026, 8, 30),
                    "units": trip.mileage_units if trip else 1,
                    "mileage": trip.one_way_miles if trip else Decimal("1.00"),
                    "charge": claim.total_charge or Decimal("50.00"),
                    "is_active": True,
                },
            )
            lines.append(line)
            # Second line on some claims so we still have 5+ line rows with variety
            if i < 2:
                extra, _ = ClaimServiceLine.objects.update_or_create(
                    claim=claim,
                    procedure_code="A0110",
                    defaults={
                        "from_date": trip.service_date if trip else date(2026, 8, 30),
                        "to_date": trip.service_date if trip else date(2026, 8, 30),
                        "units": 1,
                        "mileage": Decimal("0.00"),
                        "charge": Decimal("25.00"),
                        "is_active": True,
                    },
                )
                lines.append(extra)
        return lines

    def _seed_documents(self, claims):
        docs = []
        for claim in claims:
            if not claim.attachment_required:
                continue
            for doc_type, suffix, digest in (
                (DocumentType.STANDARD_TRIP_LOG, "trip_log", "HASH-TRIP"),
                (DocumentType.MILE_25_VERIFICATION, "verification", "HASH-25"),
            ):
                obj, _ = ClaimDocument.objects.update_or_create(
                    claim=claim,
                    document_type=doc_type,
                    defaults={
                        "file_name": f"{suffix}_{claim.claim_number}.pdf",
                        "document_hash": f"{digest}-{claim.claim_number}",
                        "is_signed": True,
                        "status": DocumentStatus.COMPLETE,
                        "is_active": True,
                    },
                )
                docs.append(obj)
            sync_claim_document_status(claim)
        # Ensure at least 5 document rows: add OTHER docs on non-LD claims if needed
        if len(docs) < 5:
            for claim in claims:
                if len(docs) >= 5:
                    break
                if claim.attachment_required:
                    continue
                obj, _ = ClaimDocument.objects.update_or_create(
                    claim=claim,
                    document_type=DocumentType.OTHER,
                    defaults={
                        "file_name": f"note_{claim.claim_number}.pdf",
                        "document_hash": f"HASH-OTHER-{claim.claim_number}",
                        "is_signed": True,
                        "status": DocumentStatus.COMPLETE,
                        "is_active": True,
                    },
                )
                docs.append(obj)
        return docs

    def _seed_batches(self, partners, claims):
        batches = []
        batch_claims = []
        ready_claims = [
            c
            for c in claims
            if Claim.objects.filter(
                pk=c.pk, status=ClaimStatus.READY_FOR_837P, is_active=True
            ).exists()
        ]
        for i in range(5):
            batch_number = f"DEMO-RB-2026-{10048 + i}"
            batch, _ = SubmissionBatch.objects.update_or_create(
                batch_number=batch_number,
                defaults={
                    "trading_partner": partners[i % len(partners)],
                    "environment": "TEST",
                    "status": BatchStatus.READY,
                    "is_active": True,
                },
            )
            batches.append(batch)

        # Put first ready claim into first batch (Ali-style demo)
        if ready_claims:
            claim = ready_claims[0]
            existing = BatchClaim.objects.filter(
                batch=batches[0], claim=claim
            ).first()
            if existing is None:
                try:
                    row = add_claim_to_batch(
                        batch_id=batches[0].id,
                        claim_id=claim.id,
                        st02="0001",
                    )
                    batch_claims.append(row)
                except ValueError:
                    pass
            else:
                batch_claims.append(existing)

        # Fill remaining batch_claims with other ready claims across batches
        idx = 1
        for claim in ready_claims[1:]:
            if idx >= len(batches):
                break
            batch = batches[idx]
            if BatchClaim.objects.filter(batch=batch, claim=claim).exists():
                batch_claims.append(
                    BatchClaim.objects.get(batch=batch, claim=claim)
                )
            else:
                try:
                    row = add_claim_to_batch(
                        batch_id=batch.id,
                        claim_id=claim.id,
                    )
                    batch_claims.append(row)
                except ValueError:
                    pass
            idx += 1

        for batch in batches:
            refresh_batch_totals(batch)

        return batches, batch_claims

    def _seed_edi(self, batches):
        controls = []
        files = []
        for i, batch in enumerate(batches):
            batch.refresh_from_db()
            if batch.claim_count < 1:
                continue

            existing_file = EDIFile.objects.filter(
                batch=batch, is_active=True
            ).first()
            if existing_file is not None:
                files.append(existing_file)
                if existing_file.control_number_id:
                    controls.append(existing_file.control_number)
                continue

            try:
                edi = create_edi_file_for_batch(
                    batch_id=batch.id,
                    file_hash=f"DEMO-FILEHASH-{i + 1:03d}",
                    path_or_blob_ref=f"s3://edi/demo/{batch.batch_number}.txt",
                    status=EDIFileStatus.GENERATED,
                )
                edi = mark_edi_file_uploaded(
                    edi.id,
                    path_or_blob_ref=edi.path_or_blob_ref,
                    file_hash=edi.file_hash,
                )
                files.append(edi)
                if edi.control_number_id:
                    controls.append(edi.control_number)
            except ValueError:
                continue
        return controls, files

    def _seed_sftp(self, partners):
        creds = []
        dirs = []
        for i in range(5):
            name = f"DEMO-SFTP-{i + 1:02d}"
            cred, _ = SFTPCredentials.objects.update_or_create(
                name=name,
                environment="TEST",
                defaults={
                    "trading_partner": partners[i % len(partners)],
                    "host": f"mft-demo-{i + 1}.example.com",
                    "port": 22,
                    "username": f"demo_user_{i + 1}",
                    "auth_type": SFTPAuthType.PASSWORD,
                    "password": f"DEMO-ONLY-PASSWORD-{i + 1}",
                    "timeout_seconds": 30,
                    "notes": "Demo SFTP credentials — not real.",
                    "is_active": True,
                },
            )
            creds.append(cred)
            directory, _ = SFTPDirectory.objects.update_or_create(
                credentials=cred,
                purpose=SFTPDirectoryPurpose.OUTBOUND_837P,
                sending_path=f"/demo/outbound/837p/{i + 1}",
                receiving_path=f"/demo/inbound/999/{i + 1}",
                defaults={
                    "name": f"DEMO outbound {i + 1}",
                    "is_active": True,
                },
            )
            dirs.append(directory)
        return creds, dirs
