# RedArt EDI — Progress Report

**Branch:** `Ayaz/local-main`  
**Date:** 2026-08-31  
**Role:** Standalone EDI API service (not copied into RedArt). RedArt backend calls this service.

**Flow:** `RedArt UI → RedArt backend → EDI API (/api/v1) → HCPF MFT/SFTP`

---

## Done (ready for RedArt integration)

| Area | Status |
|------|--------|
| Provider / patient / trip / claim / service lines / documents / batches | Done |
| Long-distance document gate (25+ / 52–125) | Done |
| `POST /claims/{id}/validate/` → `{ready, errors[]}` | Done |
| `GET /claims/{id}/status/` + `GET /submission-batches/{id}/status/` | Done |
| 837P generate (client-approved sample shape) | Done |
| Upload to HCPF SFTP + MinIO + transfer logs | Done |
| 999 import (paste + SFTP poll) / apply (never sets PAID) | Done |
| 835 remittance import → Claim PAID / DENIED (CLP-driven) | Done |
| JWT auth: `POST /api/v1/auth/token/` (+ refresh/verify) | Done |
| API service user (`create_api_service_user`, group `edi_api_service`) | Done |
| Sample curl pack: `docs/REDART_API_SAMPLES.md` | Done |
| Swagger: `/api/docs/` · versioned `/api/v1/` | Done |
| HCPF TP enrollment + real MFT key SFTP wired (TEST) | Done |

### What Wahab needs from this service
1. **API URL** (TEST/deployed host)  
2. **Auth** — service user credentials (secure channel) → `POST /api/v1/auth/token/` → `Authorization: Bearer <access>`  
3. **Swagger** — `/api/docs/`  
4. **Sample payloads** — `docs/REDART_API_SAMPLES.md` + seed (`seed_demo_data --flush-all`)

Local Docker: `http://127.0.0.1:7000`  
Enforce auth in Docker/local: `API_REQUIRE_AUTH=true`

---

## Remaining

| # | Item | Owner / note |
|---|------|----------------|
| 1 | Deployed TEST API URL + service user credential (secure delivery) | Ops / cloud |
| 2 | Confirm HCPF picked up test 837P + import returned 999 | Ops / wait on HCPF |
| 3 | Stronger production 837P TR3 coverage | EDI eng (demo OK now) |
| 4 | Live HCPF attachment channel send | Later (tracking exists) |
| 5 | Production hardening (`API_REQUIRE_AUTH`, HTTPS, secrets) | Deploy |
| 6 | 835 SFTP auto-poll (import-paste done) | Later |

**Roughly 5–6 remaining items** — cloud TEST URL still ops. 835 paste-import paid/denied is ready.

---

## Not remaining (architecture already correct)

- RedArt does **not** embed this codebase  
- RedArt does **not** generate X12 or hold SFTP keys  
- This service is the EDI engine behind RedArt’s backend  
