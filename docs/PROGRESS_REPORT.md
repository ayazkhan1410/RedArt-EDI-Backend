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
| JWT auth: `POST /api/v1/auth/token/` (+ refresh/verify) | Done |
| Swagger: `/api/docs/` · versioned `/api/v1/` | Done |
| HCPF TP enrollment + real MFT key SFTP wired (TEST) | Done |

### What Wahab needs from this service
1. **API URL** (TEST/deployed host)  
2. **Auth** — create service user → `POST /api/v1/auth/token/` → `Authorization: Bearer <access>`  
3. **Swagger** — `/api/docs/`  
4. **Sample payloads** — Swagger examples + seed data (`seed_demo_data --flush-all`)

Local Docker: `http://127.0.0.1:7000`  
Enforce auth in Docker/local: `API_REQUIRE_AUTH=true`

---

## Remaining

| # | Item | Owner / note |
|---|------|----------------|
| 1 | Deployed TEST API URL + service user credential (secure delivery) | Ops / EDI eng |
| 2 | Sample request/response pack (one-pager for RedArt) | EDI eng |
| 3 | Confirm HCPF picked up test 837P + import returned 999 | Ops / wait on HCPF |
| 4 | Stronger production 837P TR3 coverage | EDI eng (demo OK now) |
| 5 | 835 paid/denied processing | Later (handoff PDF) |
| 6 | Live HCPF attachment channel send | Later (tracking exists) |
| 7 | Production hardening (`API_REQUIRE_AUTH`, HTTPS, secrets) | Deploy |

**Roughly 7 remaining items** — **3 are required before RedArt connects** (#1–#2, plus #7 for any shared TEST). #3–#6 can continue in parallel.

---

## Not remaining (architecture already correct)

- RedArt does **not** embed this codebase  
- RedArt does **not** generate X12 or hold SFTP keys  
- This service is the EDI engine behind RedArt’s backend  
