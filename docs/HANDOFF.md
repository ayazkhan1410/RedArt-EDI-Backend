# RedArt EDI Backend — Handoff

Use this on any machine. Open a **new** Cursor chat and say:

> Read `docs/HANDOFF.md` and `.cursor/rules/edi-project.mdc`, then continue from **Next to build**.

Branch: **`Ayaz/local-main`**  
Repo: https://github.com/ayazkhan1410/RedArt-EDI-Backend

---

## What this project is

Django/DRF microservice for **RedArt Digital** (NEMT) to replace Colorado Medicaid portal/robot billing with **HIPAA X12 837P** batch EDI.

- Trading Partner ≠ Provider Billing Profile (submitter vs billing provider)
- Long-distance claims need **documents + 837P**; attachments use a **separate HCPF-approved channel** (not “PDF stuffed into batch EDI” unless HCPF confirms)
- Demo story: trips → claims → batch → 837P → control numbers → 999; attachments tracked separately

Key PDFs (local, gitignored `*.pdf`):

- Colorado EDI / 837 companion + RedArt developer guides
- `RedArt_52Plus_NEMT_Attachment_Workflow_Developer_Guide.pdf` — 52/125 + 25+ mile docs workflow

FigJam (client):

- Claim flow: https://www.figma.com/board/OY4tDGply8fIO0yjwCLxOi
- Schema ERD: https://www.figma.com/board/M4ydMYD7L6FDqhmjDMWIZj

---

## Stack / run

- Django **5.2**, package **`redartdigital`**, apps under `apps/`
- Docker Compose: host ports **7000** backend, **7001** Postgres, **7002** Redis, **7003** Flower
- Admin/API on Docker use **Postgres**. Host `migrate` without `POSTGRES_HOST` hits **SQLite** — migrate both when needed
- Swagger: `http://127.0.0.1:7000/api/docs/`
- Health: `GET /api/health/`
- Entrypoint migrates on container **start**; new migrations while container is up → restart or migrate against `7001`
- Shell scripts must be **LF** (`.gitattributes`); CRLF breaks Docker (`bash\r`)

```bash
git checkout Ayaz/local-main && git pull
docker compose up -d
# After model changes (example against Docker Postgres from host):
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=7001 POSTGRES_DB=edi POSTGRES_USER=edi POSTGRES_PASSWORD=edi POSTGRES_SSLMODE=disable \
  python manage.py migrate
```

---

## Built so far (apps)

| App | Purpose |
|-----|---------|
| `apps.core` | `BaseModel`, `StandardPagination`, `utils.responses`, `seed_demo_data` |
| `apps.trading_partner` | EDI submitter (sender_id / receiver_id / environment) |
| `apps.provider_billing_profile` | Billing NPI identity (+ location_id, revalidation_date, address…) |
| `apps.patient` | Member; **`county`** drives 52 vs 125 |
| `apps.nemt_trip` | Ride; FKs patient + provider; long-distance-check API |
| `apps.long_distance_rule` | DB rules STANDARD 52/25, DESIGNATED_RURAL 125/25 (seeded) |
| `apps.claim` | Claim (trip_id only); **ClaimDocument**; **SubmissionBatch** / **BatchClaim**; create-from-trip + doc completeness / block batch add |
| `apps.claim_service_line` | Billable lines (procedure / units / mileage / charge) |

API mount: single include → `redartdigital/api_v1_urls.py` under `/api/v1/`.

Useful endpoints:

- `/api/v1/trading-partners/`
- `/api/v1/provider-billing-profiles/`
- `/api/v1/patients/`
- `/api/v1/nemt-trips/` + `/api/v1/nemt-trips/<id>/long-distance-check/`
- `/api/v1/long-distance-rules/`
- `/api/v1/claims/` + `/api/v1/claims/from-trip/` + `/api/v1/claims/<id>/document-status/`
- `/api/v1/claim-documents/`
- `/api/v1/submission-batches/` + `/api/v1/submission-batches/<id>/add-claim/`
- `/api/v1/batch-claims/`
- `/api/v1/claim-service-lines/`

Patterns in place:

- Soft delete default; `?hard=true` for hard delete
- Writes return `{success, message, data: {id}}`; GET returns full object
- Swagger tags per app; sample request bodies on writes
- Pagination: `apps.core.pagination.StandardPagination` (reject `page=abc`)
- NEMT trips: `NemtTrip.objects.with_relations()` → `select_related("patient", "provider")` (no N+1)
- Helpers in `utils/` (`service.py`, `validators.py`, `mileage.py`); serializers = validation only

---

## Locked schema decisions (not all coded yet)

**Claim** → only `trip_id` (patient/provider via trip).  
**Claim.status** (business) ≠ **EDIFile.status** (transport).  
**ClaimDocument** = files; **AttachmentSubmission** = transmission channel/reference.  
**LongDistanceRule** in DB (done). Rural county list still empty in `DESIGNATED_RURAL_COUNTIES` — until filled, everyone is STANDARD.

Planned entities still to build: ClaimDocument, AttachmentSubmission, SubmissionBatch, BatchClaim, EDIFile, EDIControlNumber, EDIAcknowledgement.

Claim flags when coding: `attachment_required`, `attachment_route`, `attachment_status`, `external_id`, diagnosis, POS, etc.  
EDIFile: `status`, `uploaded_at`, `path`/`blob_ref`. BatchClaim: `st02`. EDIControlNumber: `environment`. EDIAcknowledgement: `affected_st02`, `raw_file_ref`.

---

## Long-distance logic (Ali 78 miles)

1. `one_way_miles > verification_threshold` (25) → need 25+ Mile Verification Form  
2. Resolve county type → load **LongDistanceRule** (52 or 125)  
3. `mileage_units > review_threshold` → long-distance review / `attachment_required`  
4. Incomplete docs → **block** submit  
5. Complete → generate/send **837P**; attachments on **separate approved channel**; track `AttachmentSubmission`

Do **not** re-decide `attachment_required` after 999 — set at rules stage and reuse.

---

## Next to build

1. Populate rural counties (or county table) so DESIGNATED_RURAL actually applies  
2. AttachmentSubmission (separate channel tracking; ClaimDocument already exists)  
3. EDIFile / control numbers / 999  
4. Validator + 837P generator APIs  
5. Service auth for RedArt → EDI  

Build model-by-model: propose → approve → code → migrate when asked.

---

## Ubuntu laptop checklist

1. Clone/pull `Ayaz/local-main`  
2. Copy `.env` from office (never commit secrets) or recreate from `.env.example`  
3. Docker Desktop / Compose on Ubuntu  
4. New Cursor chat → point at `docs/HANDOFF.md`  
5. If chat feels “dumb,” this office chat still has full history — use either
