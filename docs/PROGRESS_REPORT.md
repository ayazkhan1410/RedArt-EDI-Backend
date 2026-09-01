# RedArt EDI — Progress Report

**Branch:** `Ayaz/local-main`  
**Date:** 2026-09-01  
**Role:** Standalone EDI API service. RedArt backend calls this service.

**Flow:** `RedArt UI → RedArt backend → EDI API (/api/v1) → HCPF MFT/SFTP`

---

## Done (ready for RedArt integration)

| Area | Status |
|------|--------|
| Provider / patient / trip / claim / service lines / documents / batches | Done |
| Long-distance document gate (25+ / 52–125) | Done |
| Document blob storage + upload/download APIs | Done |
| Attachment queue + dashboard + bulk review API | Done |
| Production MFT attachment adapter (portal + SFTP) | Done |
| Document `service_date` + `verification_date` fields | Done |
| `POST /claims/{id}/validate/` + status endpoints | Done |
| 837P generate + SFTP upload + transfer logs | Done |
| 999 import (paste + SFTP poll) | Done |
| 277 import (paste + SFTP poll) | Done |
| Edifecs validation reports (audit/LDNS XML) | Done |
| Long-distance pilot API (`POST /pilot/long-distance/`) | Done |
| 835 remittance import + SFTP poll | Done |
| JWT auth + API service user | Done |
| Swagger `/api/docs/` + sample payloads | Done |
| HCPF TEST SFTP wired | Done |

### What Wahab needs
1. **Deployed TEST API URL** (Render or similar)
2. **Auth** — `POST /api/v1/auth/token/` → Bearer token
3. **Swagger** — `/api/docs/`
4. **Sample payloads** — `docs/REDART_API_SAMPLES.md`

Local Docker: `http://127.0.0.1:7000`

---

## Remaining (ops / client)

| # | Item | Owner |
|---|------|-------|
| 1 | Deploy TEST API URL + hand off credentials | Ops |
| 2 | Confirm live HCPF 837P pickup + 999 + Edifecs reports | Ops / HCPF |
| 3 | HCPF attachment channel confirmation (if not MFT) | Client / HCPF |
| 4 | Run long-distance pilot against HCPF TEST with signed docs | Ops |

---

## Key endpoints (integration)

| Step | Endpoint |
|------|----------|
| Upload docs | `POST /api/v1/claim-documents/upload/` |
| Bulk attachment ops | `POST /api/v1/attachment-submissions/bulk-review/` |
| LD pilot | `POST /api/v1/pilot/long-distance/` |
| Import 999 | `POST /api/v1/edi-acknowledgements/import-999/` or `edi-999-imports/poll/` |
| Import 277 | `POST /api/v1/edi-acknowledgements/import-277/` or `edi-277-imports/poll/` |
| Validation reports | `POST /api/v1/edi-validation-reports/import/` |

Production attachment settings (when `ATTACHMENT_PRODUCTION_MODE=true`):

- `ATTACHMENT_MFT_ENABLED=true`
- `ATTACHMENT_PRODUCTION_DEFAULT_CHANNEL=HCPF_APPROVED_CHANNEL`
- `ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE={claim_number}/{document_type}/{filename}`
- Active `OUTBOUND_ATTACHMENT` SFTP directory for `PRODUCTION`

---

## Not in this repo

- RedArt frontend (`RedArt-EDI-Frontend`)
- RedArt-side API client (Wahab integrates from RedArt backend)
