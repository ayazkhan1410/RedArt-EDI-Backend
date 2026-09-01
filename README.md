# RedArt EDI Backend

Django REST microservice for **Colorado Medicaid NEMT** — HIPAA **X12 837P** generation, batching, SFTP/MFT transport, acknowledgements (999/277), remittance (835), and long-distance attachment workflow.

**Architecture:** RedArt UI → RedArt backend → **this API** (`/api/v1/`) → HCPF (SFTP/MFT).  
This repo is the **EDI backend only** — not the RedArt frontend or RedArt’s main application.

| Resource | Location |
|----------|----------|
| API handoff (integration contract) | `RedArt_EDI_API_Integration_Handoff.pdf` |
| Long-distance attachment guide | `RedArt_52Plus_NEMT_Attachment_Workflow_Developer_Guide.pdf` |
| Integration samples | `docs/REDART_API_SAMPLES.md` |
| Agent / dev context | `docs/HANDOFF.md` |
| Progress snapshot | `docs/PROGRESS_REPORT.md` |
| Integration architecture (FigJam) | https://www.figma.com/board/qM4zo4vMIAJioyLQsetRkm |
| Backend status diagram (FigJam) | https://www.figma.com/board/BON1SRPbQOvxHhDWFnDpr8 |

**Branch:** `Ayaz/local-main` · **Repo:** https://github.com/ayazkhan1410/RedArt-EDI-Backend

---

## Task status summary

| Source | Done | Remaining |
|--------|------|-----------|
| API Integration Handoff (backend scope) | 18 | 4 |
| Attachment Workflow Guide (Steps 1–5, 7 scaffold) | 6 | 2 |
| Handoff “Definition of Done” (11-step TEST flow) | 10 | 1 |
| **Client / RedArt integration** (separate repo) | — | 6 |
| **DevOps / HCPF live TEST** | — | 4 |

**Legend:** ✅ Done in this repo · ❌ Not done / outside this repo · ⚠️ Partial / pending external confirmation

**Owners:** **Backend** = this EDI API · **Client** = RedArt app / Wahab integration · **DevOps** = deploy, secrets, SFTP ops · **HCPF** = Colorado Medicaid / channel confirmation

---

## API Integration Handoff (`RedArt_EDI_API_Integration_Handoff.pdf`)

### EDI developer deliverables (this repo)

| # | Task | Status | Owner |
|---|------|--------|-------|
| 1 | REST API under `/api/v1/` (versioned routes) | ✅ | Backend |
| 2 | Patients, providers, trips, claims, service lines CRUD | ✅ | Backend |
| 3 | Claim validate / readiness (`POST /claims/{id}/validate/`) | ✅ | Backend |
| 4 | Submission batches + add claim to batch | ✅ | Backend |
| 5 | 837P generate + queue upload (`POST /edi-files/generate-837p/`) | ✅ | Backend |
| 6 | Claim & batch status endpoints | ✅ | Backend |
| 7 | JWT service-to-service auth (`POST /auth/token/`) | ✅ | Backend |
| 8 | Swagger / OpenAPI (`/api/docs/`) | ✅ | Backend |
| 9 | Sample payloads (`docs/REDART_API_SAMPLES.md`) | ✅ | Backend |
| 10 | Structured validation errors for RedArt UI | ✅ | Backend |
| 11 | 999 import (paste + SFTP poll) | ✅ | Backend |
| 12 | 835 remittance import + SFTP poll | ✅ | Backend |
| 13 | 277 status import (paste + SFTP poll) | ✅ | Backend |
| 14 | Edifecs validation reports (audit / LDNS XML) | ✅ | Backend |
| 15 | TEST vs PRODUCTION via trading partner / environment | ✅ | Backend |
| 16 | Idempotent guards (duplicate attachment, 835 hash, etc.) | ✅ | Backend |
| 17 | Document upload API (blobs, not X12 in RedArt) | ✅ | Backend |
| 18 | Integration catalog (`GET /integration/lovable/`) | ✅ | Backend |
| 19 | **Production TEST API URL** (public HTTPS base URL) | ❌ | DevOps |
| 20 | **Live HCPF TEST** (837P pickup → 999 → Edifecs reports) | ❌ | DevOps / HCPF |
| 21 | Deliver TEST credentials to Wahab securely | ❌ | DevOps |
| 22 | **RedArt backend wired to this API** | ❌ | Client |

*Note:* Handoff shows `POST /submission-batches/{id}/submit/` as illustrative. This codebase uses **`POST /api/v1/edi-files/generate-837p/`** (+ optional upload queue) after the batch is ready — same intent, stable contract in Swagger.*

### RedArt integration side (not this repo)

| # | Task | Status | Owner |
|---|------|--------|-------|
| 1 | Map RedArt bill/trip fields to EDI API payloads | ❌ | Client |
| 2 | Display validation / status in RedArt UI | ❌ | Client |
| 3 | Server-to-server auth (no secrets in browser) | ❌ | Client |
| 4 | UI status mapping (Ready → Submitted → Paid, etc.) | ❌ | Client |
| 5 | Trigger validate / batch / status from RedArt workflows | ❌ | Client |
| 6 | Reconcile via `external_id` / claim numbers | ❌ | Client |

### Definition of Done — 11-step TEST flow (backend capability)

| Step | Task | Status | Owner |
|------|------|--------|-------|
| 1 | Create/sync provider | ✅ | Backend |
| 2 | Create/sync patient | ✅ | Backend |
| 3 | Create trip | ✅ | Backend |
| 4 | Create claim + service lines | ✅ | Backend |
| 5 | Attach / record supporting documents | ✅ | Backend |
| 6 | Run validation | ✅ | Backend |
| 7 | Receive READY result | ✅ | Backend |
| 8 | Create submission batch | ✅ | Backend |
| 9 | Trigger TEST generation / upload | ✅ | Backend |
| 10 | Read acknowledgement / status | ✅ | Backend |
| 11 | **Re-query claim on deployed TEST URL** (end-to-end with HCPF) | ❌ | DevOps |

---

## Attachment Workflow Guide (`RedArt_52Plus_NEMT_Attachment_Workflow_Developer_Guide.pdf`)

| # | Task | Status | Owner |
|---|------|--------|-------|
| **Step 1** | Mileage threshold + county routing (`LongDistanceRule`, flags on claim) | ✅ | Backend |
| **Step 2** | Standard Trip Log + 25+ Verification fields (`ClaimDocument`, dates) | ✅ | Backend |
| **Step 3** | Document completeness validation + submission blocking | ✅ | Backend |
| **Step 4** | Attachment Required queue + statuses + dashboard | ✅ | Backend |
| **Step 5** | 837P generation separate from attachment channel | ✅ | Backend |
| **Step 6** | Ask HCPF approved attachment / correlation method | ❌ | Client / HCPF |
| **Step 7** | Production attachment adapter (portal + MFT scaffold) | ⚠️ | Backend* |
| **Step 8** | Pilot test with real long-distance claims on TEST | ❌ | DevOps / Ops |
| A | Long-distance rules engine (25+ / 52 / 125 rural) | ✅ | Backend |
| B | Document package per claim (blob, hash, signed, dates) | ✅ | Backend |
| C | Submission blocker when docs incomplete | ✅ | Backend |
| — | Attachment queue + bulk review API | ✅ | Backend |
| — | Duplicate attachment protection (payload hash) | ✅ | Backend |
| — | Portal adapter + MFT adapter (`ATTACHMENT_PRODUCTION_MODE`) | ✅ | Backend |
| — | Long-distance pilot API (`POST /pilot/long-distance/`) | ✅ | Backend |
| — | Claim statuses (DRAFT → DOCUMENTS_REQUIRED → … → PAID) | ✅ | Backend |
| — | RedArt UI for attachment queue / bulk ops | ❌ | Client |

\*Step 7: **MFT adapter and portal path are implemented**; **HCPF must confirm** production channel and correlation IDs before bulk production use (PDF §10–11).

---

## Stack

- Django **5.2** + DRF, apps under `apps/`
- PostgreSQL, Redis, Celery + Beat, MinIO/S3
- Docker Compose: API **7000**, Postgres **7001**, Redis **7002**, Flower **7003**

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d
docker compose exec backend python manage.py migrate
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:7000/api/health/ | Health |
| http://127.0.0.1:7000/api/docs/ | Swagger |
| http://127.0.0.1:7000/admin/ | Django admin |

See **`.env.example`** for Dev vs Prod required variables.

## Key integration endpoints

| Step | Endpoint |
|------|----------|
| Auth | `POST /api/v1/auth/token/` |
| Upload document | `POST /api/v1/claim-documents/upload/` |
| Validate claim | `POST /api/v1/claims/{id}/validate/` |
| Claim status | `GET /api/v1/claims/{id}/status/` |
| Attachment queue | `GET /api/v1/claims/attachment-queue/` |
| Attachment dashboard | `GET /api/v1/claims/attachment-dashboard/` |
| Submit attachments | `POST /api/v1/attachment-submissions/submit/` |
| Bulk attachment ops | `POST /api/v1/attachment-submissions/bulk-review/` |
| Generate 837P | `POST /api/v1/edi-files/generate-837p/` |
| Import 999 / poll | `POST /api/v1/edi-acknowledgements/import-999/` · `POST /api/v1/edi-999-imports/poll/` |
| Import 277 / poll | `POST /api/v1/edi-acknowledgements/import-277/` · `POST /api/v1/edi-277-imports/poll/` |
| Long-distance pilot | `POST /api/v1/pilot/long-distance/` |

Full examples: `docs/REDART_API_SAMPLES.md`

## Settings

| Module | Use |
|--------|-----|
| `redartdigital.settings.local` | Local / dev |
| `redartdigital.settings.docker` | Docker Compose |
| `redartdigital.settings.production` | Production deploy |

## Tests

```bash
docker compose exec backend python manage.py test apps
```

## License

Proprietary — RedArt LLC. All rights reserved.
