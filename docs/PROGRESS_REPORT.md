# RedArt EDI — Progress Report

**Branch:** `Ayaz/local-main`  
**Date:** 2026-09-01  
**Role:** Standalone EDI API service. RedArt backend (or Lovable-hosted deploy) calls this service.

**Flow:** `RedArt UI → RedArt backend / Lovable → EDI API (/api/v1) → HCPF MFT/SFTP`

**FigJam diagrams (share with client):**

| Diagram | Link |
|---------|------|
| Integration architecture | https://www.figma.com/board/qM4zo4vMIAJioyLQsetRkm |
| Backend status (done vs remaining) | https://www.figma.com/board/BON1SRPbQOvxHhDWFnDpr8 |

---

## Summary

| Scope | Done | Remaining |
|-------|------|-----------|
| **Backend (this repo)** | 28 | 2* |
| **Client integration** | 0 | 6 |
| **DevOps / HCPF live TEST** | 0 | 4 |

\*Backend code is complete; deployed TEST URL and live HCPF round-trip are deployment/ops, not missing features.

**Tests:** 176 passing (`docker compose exec backend python manage.py test apps`)

---

## Backend — Done ✅

| # | Area | Status | Notes |
|---|------|--------|-------|
| 1 | REST API `/api/v1/` | ✅ | Versioned routes in `redartdigital/api_v1_urls.py` |
| 2 | Patients, providers, trips, claims, service lines CRUD | ✅ | Soft delete, pagination |
| 3 | Claim documents + blob upload/download | ✅ | MinIO/S3; not X12 in client apps |
| 4 | Submission batches | ✅ | Add claims, batch status |
| 5 | `POST /claims/{id}/validate/` | ✅ | Readiness + structured errors |
| 6 | Claim & batch status endpoints | ✅ | `GET /claims/{id}/status/` |
| 7 | 837P generate + SFTP upload queue | ✅ | `POST /edi-files/generate-837p/` |
| 8 | 999 import (paste + SFTP poll) | ✅ | Claim status sync optional |
| 9 | 277 import (paste + SFTP poll) | ✅ | Auth status on claims |
| 10 | 835 remittance import + SFTP poll | ✅ | Idempotent hash guard |
| 11 | Edifecs validation reports | ✅ | Audit + LDNS XML import |
| 12 | Long-distance rules engine | ✅ | `LongDistanceRule` DB (25+ / 52 / 125 rural) |
| 13 | Attachment queue + dashboard | ✅ | Statuses, filters, counts |
| 14 | Attachment submit + bulk review | ✅ | `bulk-review/` for ops |
| 15 | Production MFT attachment adapter | ✅ | Portal + SFTP scaffold (`ATTACHMENT_PRODUCTION_MODE`) |
| 16 | Document `service_date` + `verification_date` | ✅ | Migration `claim.0006` |
| 17 | Duplicate attachment protection | ✅ | Payload hash idempotency |
| 18 | Long-distance pilot API | ✅ | `POST /pilot/long-distance/` |
| 19 | JWT auth | ✅ | `POST /auth/token/` + blacklist |
| 20 | Swagger `/api/docs/` | ✅ | OpenAPI 3 |
| 21 | Sample payloads | ✅ | `docs/REDART_API_SAMPLES.md` |
| 22 | Integration catalog | ✅ | `GET /integration/lovable/` |
| 23 | TEST vs PRODUCTION environments | ✅ | Trading partner + env flags |
| 24 | Security hardening | ✅ | Serializer locks, upload limits, permissions |
| 25 | `.env.example` Dev/Prod sections | ✅ | Required vars documented |
| 26 | Celery + Beat (poll tasks) | ✅ | 999/277/835 SFTP poll |
| 27 | HCPF TEST SFTP wiring (local/docker) | ✅ | Env-driven directories |
| 28 | Definition of Done steps 1–10 | ✅ | Local/docker end-to-end |

---

## Backend — Remaining ❌ / ⚠️

| # | Item | Status | Owner | Notes |
|---|------|--------|-------|-------|
| 1 | **Production TEST API URL** (public HTTPS) | ❌ | DevOps / Lovable | API ready; needs deploy + base URL |
| 2 | **Live HCPF TEST** (837P pickup → 999 → Edifecs) | ❌ | DevOps / HCPF | After deploy + credentials |
| 3 | Deliver TEST credentials securely | ❌ | DevOps | JWT user + SFTP if needed |
| 4 | HCPF attachment channel confirmation | ⚠️ | Client / HCPF | MFT scaffold exists; confirm production channel |
| 5 | Long-distance pilot on HCPF TEST (signed docs) | ❌ | Ops | After deploy |

---

## Client integration — Remaining ❌ (not this repo)

| # | Item | Owner |
|---|------|-------|
| 1 | Map RedArt bill/trip fields to EDI API payloads | Client |
| 2 | Server-to-server auth (no secrets in browser) | Client |
| 3 | Display validation / claim status in RedArt UI | Client |
| 4 | UI status mapping (Ready → Submitted → Paid) | Client |
| 5 | Trigger validate / batch / status from workflows | Client |
| 6 | RedArt UI for attachment queue / bulk ops | Client |

**Lovable:** can host/deploy this API stack (Render-style) — use `GET /integration/lovable/` catalog and `docs/REDART_API_SAMPLES.md` for wiring.

---

## API Integration Handoff — Definition of Done (11 steps)

| Step | Task | Status | Owner |
|------|------|--------|-------|
| 1 | Create/sync provider | ✅ | Backend |
| 2 | Create/sync patient | ✅ | Backend |
| 3 | Create trip | ✅ | Backend |
| 4 | Create claim + service lines | ✅ | Backend |
| 5 | Attach supporting documents | ✅ | Backend |
| 6 | Run validation | ✅ | Backend |
| 7 | Receive READY result | ✅ | Backend |
| 8 | Create submission batch | ✅ | Backend |
| 9 | Trigger TEST generation / upload | ✅ | Backend |
| 10 | Read acknowledgement / status | ✅ | Backend |
| 11 | Re-query claim on **deployed** TEST with HCPF | ❌ | DevOps |

---

## Attachment Workflow Guide — Steps 1–8

| Step | Task | Status | Owner |
|------|------|--------|-------|
| 1 | Mileage threshold + county routing | ✅ | Backend |
| 2 | Trip Log + Verification fields + dates | ✅ | Backend |
| 3 | Document completeness + blocking | ✅ | Backend |
| 4 | Attachment queue + statuses + dashboard | ✅ | Backend |
| 5 | 837P separate from attachment channel | ✅ | Backend |
| 6 | Ask HCPF approved attachment method | ❌ | Client / HCPF |
| 7 | Production adapter (portal + MFT) | ⚠️ | Backend* |
| 8 | Pilot with real long-distance TEST claims | ❌ | DevOps / Ops |

\*Adapter implemented; HCPF must confirm channel before bulk production use.

---

## What the client needs to integrate

1. **Deployed TEST API URL** — Lovable or Render (Docker image in repo)
2. **Auth** — `POST /api/v1/auth/token/` → Bearer on all calls
3. **Swagger** — `https://<host>/api/docs/`
4. **Samples** — `docs/REDART_API_SAMPLES.md`
5. **Integration catalog** — `GET /api/v1/integration/lovable/`

Local Docker: `http://127.0.0.1:7000`

---

## Key endpoints

| Step | Endpoint |
|------|----------|
| Auth | `POST /api/v1/auth/token/` |
| Upload docs | `POST /api/v1/claim-documents/upload/` |
| Validate | `POST /api/v1/claims/{id}/validate/` |
| Claim status | `GET /api/v1/claims/{id}/status/` |
| Attachment queue | `GET /api/v1/claims/attachment-queue/` |
| Attachment dashboard | `GET /api/v1/claims/attachment-dashboard/` |
| Submit attachments | `POST /api/v1/attachment-submissions/submit/` |
| Bulk attachment ops | `POST /api/v1/attachment-submissions/bulk-review/` |
| Generate 837P | `POST /api/v1/edi-files/generate-837p/` |
| Import 999 / poll | `POST /api/v1/edi-acknowledgements/import-999/` · `POST /api/v1/edi-999-imports/poll/` |
| Import 277 / poll | `POST /api/v1/edi-acknowledgements/import-277/` · `POST /api/v1/edi-277-imports/poll/` |
| Validation reports | `POST /api/v1/edi-validation-reports/import/` |
| Long-distance pilot | `POST /api/v1/pilot/long-distance/` |
| Lovable catalog | `GET /api/v1/integration/lovable/` |

Production attachment (when `ATTACHMENT_PRODUCTION_MODE=true`):

- `ATTACHMENT_MFT_ENABLED=true`
- `ATTACHMENT_PRODUCTION_DEFAULT_CHANNEL=HCPF_APPROVED_CHANNEL`
- `ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE={claim_number}/{document_type}/{filename}`
- Active `OUTBOUND_ATTACHMENT` SFTP directory for `PRODUCTION`

---

## Not in this repo

- RedArt frontend (`RedArt-EDI-Frontend`)
- RedArt-side API client (client team integrates from their backend or Lovable)
