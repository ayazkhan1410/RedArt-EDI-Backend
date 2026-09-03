# RedArt EDI API — Complete User Guide

**Audience:** RedArt backend developers, integration engineers, QA, and DevOps  
**API version:** `v1`  
**Base path:** `/api/v1/`  
**Branch:** `Ayaz/local-main`  
**Repo:** https://github.com/ayazkhan1410/RedArt-EDI-Backend

This guide is the primary reference for calling the RedArt EDI backend. For copy-paste curl examples, see [`REDART_API_SAMPLES.md`](REDART_API_SAMPLES.md). For deployment, see [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md).

---

## Table of contents

1. [What this service does](#1-what-this-service-does)
2. [Architecture](#2-architecture)
3. [Quick start (local)](#3-quick-start-local)
4. [Authentication](#4-authentication)
5. [Response format](#5-response-format)
6. [Errors and HTTP status codes](#6-errors-and-http-status-codes)
7. [Pagination and filtering](#7-pagination-and-filtering)
8. [Soft delete and hard delete](#8-soft-delete-and-hard-delete)
9. [End-to-end billing workflow](#9-end-to-end-billing-workflow)
10. [Endpoint reference](#10-endpoint-reference)
11. [Claim statuses](#11-claim-statuses)
12. [Long-distance attachment workflow](#12-long-distance-attachment-workflow)
13. [EDI operations (837P, 999, 277, 835)](#13-edi-operations-837p-999-277-835)
14. [Document upload and download](#14-document-upload-and-download)
15. [Security rules for integrators](#15-security-rules-for-integrators)
16. [Swagger and OpenAPI](#16-swagger-and-openapi)
17. [Related documents](#17-related-documents)

---

## 1. What this service does

The RedArt EDI backend is a **Django REST microservice** for Colorado Medicaid **NEMT** billing:

- Stores patients, providers, trips, claims, and service lines
- Validates claim readiness (demographics, documents, service lines)
- Builds **HIPAA X12 837P** files and uploads via SFTP/MFT
- Processes **999** (acknowledgement), **277** (claim status), and **835** (remittance/payment)
- Manages **long-distance attachment** workflow (52+ / 125 rural / 25+ mile docs)

**RedArt’s main application** calls this API over HTTPS. RedArt does **not** build X12 in the browser — it sends structured JSON and files.

---

## 2. Architecture

```
RedArt UI  →  RedArt backend (server)  →  EDI API (/api/v1/)  →  HCPF SFTP/MFT
```

| Layer | Responsibility |
|-------|----------------|
| RedArt UI | User-facing billing screens |
| RedArt backend | Maps bill/trip data → API payloads; holds JWT secret |
| **This API** | Validation, 837P, batches, acks, remittance, attachments |
| HCPF | Colorado Medicaid EDI / MFT |

**TEST vs PRODUCTION:** Use `environment: "TEST"` on trading partners and batches. Never mix TEST credentials with production claims.

---

## 3. Quick start (local)

### 3.1 Start the stack

```bash
cp .env.example .env
docker compose up -d
docker compose exec backend python manage.py migrate
```

### 3.2 URLs (Docker default)

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:7000/api/health/` | Health check (no auth) |
| `http://127.0.0.1:7000/api/docs/` | Swagger UI |
| `http://127.0.0.1:7000/api/schema/` | OpenAPI JSON |
| `http://127.0.0.1:7000/api/v1/` | All business APIs |
| `http://127.0.0.1:7000/admin/` | Django admin |

### 3.3 Create API service user (one-time)

```bash
docker compose exec backend python manage.py create_api_service_user \
  --username redart_api \
  --generate-password
```

Store the printed password securely. Use it only from **RedArt’s backend**, never in browser JavaScript.

### 3.4 Obtain a token

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "username": "redart_api",
  "password": "<service-password>"
}
```

**Response (200):**

```json
{
  "refresh": "<refresh-jwt>",
  "access": "<access-jwt>",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

Use on all business calls:

```http
Authorization: Bearer <access-jwt>
```

---

## 4. Authentication

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/auth/token/` | POST | None | Obtain access + refresh tokens |
| `/api/v1/auth/token/refresh/` | POST | None | Refresh access token |
| `/api/v1/auth/token/verify/` | POST | None | Verify token validity |
| `/api/health/` | GET | None | Liveness probe |
| `/api/v1/integration/lovable/` | GET | None* | Integration catalog for Lovable |
| All other `/api/v1/*` | * | **Bearer JWT** | Business APIs |

\*Catalog is public; production may still require auth depending on settings.

**Who can get a token?**

- Users in group `edi_api_service`, or
- Django staff users

**Rate limits:** Token endpoints use `auth_burst` throttle (default 20/min). API calls use user/anon throttles in Docker/production.

**Token refresh:**

```http
POST /api/v1/auth/token/refresh/
Content-Type: application/json

{ "refresh": "<refresh-jwt>" }
```

---

## 5. Response format

Almost all business endpoints return a consistent envelope.

### 5.1 Success (single resource)

```json
{
  "success": true,
  "message": "Human-readable summary.",
  "data": { "id": 1 }
}
```

`data` may be a full object on GET (claim, patient, batch, etc.) or `{ "id": N }` on create/update/delete.

### 5.2 Success (paginated list)

```json
{
  "success": true,
  "message": "List retrieved successfully.",
  "count": 120,
  "next": "http://host/api/v1/claims/?page=2",
  "previous": null,
  "data": [ /* items */ ]
}
```

Some attachment endpoints use the same shape with `count`, `next`, `previous`, and `data`.

### 5.3 Error

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "field_name": ["Error detail."]
  }
}
```

Field-level `errors` appear on serializer validation failures (400).

---

## 6. Errors and HTTP status codes

| Code | Meaning | Typical cause |
|------|---------|---------------|
| **200** | OK | GET, PUT, PATCH, DELETE (soft), successful POST |
| **201** | Created | POST create |
| **400** | Bad request | Validation error, business rule (`ValueError`) |
| **401** | Unauthorized | Missing or invalid JWT |
| **403** | Forbidden | Hard delete without staff account |
| **404** | Not found | Invalid ID or soft-deleted record |
| **409** | Conflict | Unique constraint (duplicate claim number, etc.) |
| **429** | Too many requests | Rate limit exceeded |
| **500** | Server error | Unexpected failure (check server logs) |

**Validation endpoint** always returns **200** with `data.ready: true/false` — check `ready`, not only HTTP status.

---

## 7. Pagination and filtering

**Query parameters (lists):**

| Param | Default | Max | Description |
|-------|---------|-----|-------------|
| `page` | 1 | — | Page number (positive integer) |
| `page_size` | 50 | 200 | Items per page |

**Common filters (examples):**

| Endpoint | Filters |
|----------|---------|
| `GET /claims/` | `status`, `attachment_required`, `search` |
| `GET /nemt-trips/` | `patient`, `provider`, `service_date_from`, `service_date_to` |
| `GET /claims/attachment-queue/` | `documents_complete`, `can_submit`, `page`, `page_size` |

---

## 8. Soft delete and hard delete

**Default DELETE** = soft delete (`is_active=false`). Record no longer appears in normal GET/list.

**Hard delete** (permanent): staff only

```http
DELETE /api/v1/claims/42/?hard=true
Authorization: Bearer <token>
```

Non-staff users receive **403** for `?hard=true`.

---

## 9. End-to-end billing workflow

This is the **Definition of Done** flow from the API Integration Handoff PDF.

| Step | Action | Endpoint |
|------|--------|----------|
| 1 | Create provider | `POST /provider-billing-profiles/` |
| 2 | Create patient | `POST /patients/` |
| 3 | Create trip | `POST /nemt-trips/` |
| 4 | Create claim | `POST /claims/from-trip/` |
| 4b | Add service lines (if not auto-created) | `POST /claim-service-lines/` |
| 5 | Upload documents (long-distance) | `POST /claim-documents/upload/` |
| 6 | Validate | `POST /claims/{id}/validate/` |
| 7 | Confirm READY | Check `data.ready === true` |
| 8 | Create batch | `POST /submission-batches/` |
| 8b | Add claim to batch | `POST /submission-batches/{id}/add-claim/` |
| 9 | Generate 837P | `POST /edi-files/generate-837p/` |
| 9b | Queue SFTP upload | `POST /edi-files/{id}/upload/` |
| 10 | Read status / import 999 | `GET /claims/{id}/status/` · `POST /edi-acknowledgements/import-999/` |
| 11 | Re-query later | `GET /claims/{id}/status/` |

> **Note:** The handoff PDF shows `POST /submission-batches/{id}/submit/` as illustrative. This codebase uses **`POST /edi-files/generate-837p/`** after the batch is ready — same intent.

### 9.1 Minimal example sequence

```bash
export BASE=http://127.0.0.1:7000
export TOKEN=<access-jwt>

# 1. Patient
curl -s -X POST "$BASE/api/v1/patients/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"first_name":"JANE","last_name":"TEST","date_of_birth":"1950-01-01","gender":"F","medicaid_member_id":"Y999999","county":"Pueblo","address_line_1":"100 TEST ST","city":"PUEBLO","state":"CO","zip":"81001"}'

# 2. Provider … 3. Trip … 4. Claim (see REDART_API_SAMPLES.md for full payloads)

# 6. Validate
curl -s -X POST "$BASE/api/v1/claims/1/validate/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{}"

# 8–9. Batch + generate
curl -s -X POST "$BASE/api/v1/submission-batches/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"batch_number":"BATCH-001","trading_partner":1,"environment":"TEST"}'

curl -s -X POST "$BASE/api/v1/edi-files/generate-837p/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"batch_id":1}'
```

---

## 10. Endpoint reference

All paths are relative to **`/api/v1/`**. Methods not listed default to standard REST (GET list/detail, POST create, PUT/PATCH update, DELETE soft).

### 10.1 Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `auth/token/` | Obtain JWT |
| POST | `auth/token/refresh/` | Refresh access token |
| POST | `auth/token/verify/` | Verify token |

### 10.2 Integration discovery

| Method | Path | Description |
|--------|------|-------------|
| GET | `integration/lovable/` | Endpoint catalog, auth URL, happy-path hints for Lovable |

### 10.3 Trading partners

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `trading-partners/` | List / create EDI submitter (sender/receiver IDs) |
| GET, PUT, PATCH, DELETE | `trading-partners/{id}/` | Detail / update / delete |

**Create example:**

```json
{
  "name": "Colorado Medicaid",
  "sender_id": "TP123456",
  "receiver_id": "COMEDASSISTPROG",
  "environment": "TEST",
  "is_active": true
}
```

### 10.4 Provider billing profiles

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `provider-billing-profiles/` | Billing NPI identity |
| GET, PUT, PATCH, DELETE | `provider-billing-profiles/{id}/` | Detail |

**Important fields:** `npi`, `taxonomy_code`, `legal_name`, `billing_name`, address.

### 10.5 Patients

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `patients/` | Member demographics |
| GET, PUT, PATCH, DELETE | `patients/{id}/` | Detail |

**Required for 837P:** `medicaid_member_id`, `gender`, `address_line_1`, `city`, `state`, `zip`, `county` (drives 52 vs 125 rules).

### 10.6 NEMT trips

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `nemt-trips/` | Ride record |
| GET, PUT, PATCH, DELETE | `nemt-trips/{id}/` | Detail |
| GET | `nemt-trips/{id}/long-distance-check/` | Mileage threshold evaluation |

**Long-distance check response** includes `attachment_required`, `review_threshold`, `missing_document_types`, etc.

### 10.7 Long-distance rules

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `long-distance-rules/` | DB rules (STANDARD 52/25, DESIGNATED_RURAL 125/25) |
| GET, PUT, PATCH, DELETE | `long-distance-rules/{id}/` | Detail |

### 10.8 Claims

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `claims/` | List / create |
| POST | `claims/from-trip/` | Create claim from trip (recommended) |
| GET, PUT, PATCH, DELETE | `claims/{id}/` | Detail |
| POST | `claims/{id}/validate/` | Readiness check |
| GET | `claims/{id}/status/` | Full status payload for RedArt UI |
| GET | `claims/{id}/document-status/` | Document package snapshot |
| GET | `claims/attachment-queue/` | Paginated attachment-required queue |
| GET | `claims/attachment-dashboard/` | Aggregate counts for ops dashboard |

**Validate response:**

```json
{
  "success": true,
  "message": "Claim validation complete.",
  "data": {
    "ready": false,
    "errors": ["Required document missing: MILE_25_VERIFICATION"],
    "warnings": [],
    "claim_id": 1,
    "status": "DOCUMENTS_REQUIRED"
  }
}
```

**Create from trip:**

```json
{
  "trip_id": 1,
  "claim_number": "TESTCLAIM0001",
  "external_id": "REDART-BILL-1001",
  "diagnosis_code": "R69",
  "place_of_service": "41"
}
```

`external_id` = RedArt’s bill/trip reference for reconciliation.

### 10.9 Claim service lines

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `claim-service-lines/` | Procedure / units / charge lines |
| GET, PUT, PATCH, DELETE | `claim-service-lines/{id}/` | Detail |

### 10.10 Claim documents

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `claim-documents/` | Metadata records |
| GET, PUT, PATCH, DELETE | `claim-documents/{id}/` | Detail |
| POST | `claim-documents/upload/` | **Multipart file upload** (recommended) |
| GET | `claim-documents/{id}/file/` | Download file bytes |

### 10.11 Attachment submissions

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `attachment-submissions/` | List / create submission records |
| GET, PUT, PATCH, DELETE | `attachment-submissions/{id}/` | Detail |
| POST | `attachment-submissions/submit/` | Submit attachments for a claim (portal/MFT) |
| POST | `attachment-submissions/bulk-review/` | Bulk SUBMIT / CONFIRM / FAIL for ops |

**Bulk review body:**

```json
{
  "action": "CONFIRM",
  "submission_ids": [1, 2, 3],
  "notes": "Verified signatures"
}
```

`action`: `SUBMIT`, `CONFIRM`, or `FAIL`.

### 10.12 Submission batches

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `submission-batches/` | List / create batch |
| GET, PUT, PATCH, DELETE | `submission-batches/{id}/` | Detail |
| POST | `submission-batches/{id}/add-claim/` | Add claim (enforces readiness) |
| GET | `submission-batches/{id}/status/` | Batch + EDI file summary |

**Add claim:**

```json
{ "claim_id": 1, "st02": "0001" }
```

### 10.13 Batch claims

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `batch-claims/` | Junction batch ↔ claim |
| GET, DELETE | `batch-claims/{id}/` | Detail |

### 10.14 EDI control numbers

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `edi-control-numbers/` | ISA13 / GS06 per batch |
| POST | `edi-control-numbers/allocate/` | Allocate for a batch |
| GET, PUT, PATCH, DELETE | `edi-control-numbers/{id}/` | Detail |

### 10.15 EDI files (837P)

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `edi-files/` | List / create metadata |
| POST | `edi-files/from-batch/` | Create EDI file row for batch |
| POST | `edi-files/generate-837p/` | **Generate X12 + store file** |
| POST | `edi-files/{id}/upload/` | Queue Celery SFTP + S3 upload |
| POST | `edi-files/{id}/mark-uploaded/` | Manual upload confirmation |
| GET, PUT, PATCH, DELETE | `edi-files/{id}/` | Detail |

**Generate 837P:**

```json
{
  "batch_id": 1,
  "allocate_controls": true
}
```

**Response:**

```json
{
  "success": true,
  "message": "837P generated successfully.",
  "data": {
    "id": 1,
    "filename": "SENDER-837P-20260831120000000-1of1.txt",
    "path_or_blob_ref": "edi/837p/1/...",
    "file_hash": "sha256..."
  }
}
```

### 10.16 EDI transfer logs

| Method | Path | Description |
|--------|------|-------------|
| GET | `edi-file-transfer-logs/` | SFTP/S3 upload attempt history |
| GET | `edi-file-transfer-logs/{id}/` | Detail |

### 10.17 EDI acknowledgements (999)

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `edi-acknowledgements/` | List / create ack records |
| POST | `edi-acknowledgements/import-999/` | Paste 999 X12 content |
| POST | `edi-acknowledgements/apply/` | Apply ack to claims |
| GET, DELETE | `edi-acknowledgements/{id}/` | Detail |

### 10.18 EDI 999 SFTP import

| Method | Path | Description |
|--------|------|-------------|
| GET | `edi-999-imports/` | List import jobs |
| POST | `edi-999-imports/poll/` | Discover + queue poll from SFTP |
| GET | `edi-999-imports/{id}/` | Job detail |

**Poll body:**

```json
{
  "credentials_id": 1,
  "async_mode": true
}
```

### 10.19 EDI 277 (claim status)

| Method | Path | Description |
|--------|------|-------------|
| POST | `edi-acknowledgements/import-277/` | Paste 277 X12 |
| GET | `edi-277-imports/` | List import jobs |
| POST | `edi-277-imports/poll/` | SFTP poll |
| GET | `edi-277-imports/{id}/` | Detail |

### 10.20 EDI validation reports (Edifecs)

| Method | Path | Description |
|--------|------|-------------|
| GET | `edi-validation-reports/` | List imported reports |
| POST | `edi-validation-reports/import/` | Import audit/LDNS XML |
| GET | `edi-validation-reports/{id}/` | Detail |

### 10.21 EDI 835 remittance

| Method | Path | Description |
|--------|------|-------------|
| GET | `edi-835-remittances/` | List remittances |
| POST | `edi-835-remittances/import/` | Paste 835 content |
| GET | `edi-835-remittances/{id}/` | Detail + claim payments |

**Import body:**

```json
{
  "content": "ISA*...835...",
  "apply_claim_status": true
}
```

**CLP outcome → claim status:** PAID, DENIED, UNDER_REVIEW (see samples doc).

### 10.22 EDI 835 SFTP import

| Method | Path | Description |
|--------|------|-------------|
| GET | `edi-835-imports/` | List jobs |
| POST | `edi-835-imports/poll/` | SFTP poll |
| GET | `edi-835-imports/{id}/` | Detail |

### 10.23 SFTP credentials and directories

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `sftp-credentials/` | MFT login (secrets encrypted at rest) |
| GET, PUT, PATCH, DELETE | `sftp-credentials/{id}/` | Detail (password never returned) |
| GET, POST | `sftp-directories/` | Inbound/outbound paths |
| GET, PUT, PATCH, DELETE | `sftp-directories/{id}/` | Detail |

**Directory purposes:** `INBOUND_999`, `INBOUND_835`, `OUTBOUND_837P`, `OUTBOUND_ATTACHMENT`, `GENERAL`.

### 10.24 Long-distance pilot

| Method | Path | Description |
|--------|------|-------------|
| POST | `pilot/long-distance/` | End-to-end pilot helper for TEST long-distance claims |

Use after documents are uploaded and before/after 837P + attachment submit. See Swagger for request body.

---

## 11. Claim statuses

| Status | Meaning |
|--------|---------|
| `DRAFT` | Initial |
| `DOCUMENTS_REQUIRED` | Long-distance docs incomplete — **blocked from batch** |
| `DOCUMENTS_COMPLETE` | All required docs present |
| `READY_FOR_837P` | Passed validation |
| `EDI_GENERATED` | 837P file generated (not yet uploaded to HCPF) |
| `EDI_SENT` | 837P uploaded to HCPF SFTP/MFT |
| `EDI_ACCEPTED` | 999/TA1 accepted by HCPF |
| `EDI_REJECTED` | 999/TA1 rejected — claim needs correction before resubmission |
| `ATTACHMENT_REQUIRED` | Needs attachment channel submission |
| `ATTACHMENT_QUEUED` | Queued for attachment |
| `ATTACHMENT_SUBMITTED` | Sent via portal/MFT |
| `ATTACHMENT_CONFIRMED` | Attachment confirmed |
| `UNDER_REVIEW` | Payer review (277/835) |
| `PAID` | Paid per 835 |
| `DENIED` | Denied per 835/277 |

**Rule:** Never mark **PAID** only because 837P uploaded. Use **835** remittance or explicit adjudication.

---

## 12. Long-distance attachment workflow

Per the Attachment Workflow Developer Guide:

| Step | Feature | API |
|------|---------|-----|
| 1 | Mileage + county rules | `GET /nemt-trips/{id}/long-distance-check/` |
| 2 | Trip log + 25+ verification | `POST /claim-documents/upload/` with `document_type` |
| 3 | Completeness + blocking | `POST /claims/{id}/validate/` · batch add-claim |
| 4 | Queue + dashboard | `GET /claims/attachment-queue/` · `attachment-dashboard/` |
| 5 | 837P separate | `POST /edi-files/generate-837p/` then `attachment-submissions/submit/` |
| 6 | HCPF channel confirmation | **Client/HCPF** (not an API) |
| 7 | Production MFT | `ATTACHMENT_PRODUCTION_MODE=true` + SFTP directory |
| 8 | Pilot on TEST | `POST /pilot/long-distance/` + ops |

**Document types:**

| Value | Description |
|-------|-------------|
| `STANDARD_TRIP_LOG` | Standard trip log |
| `MILE_25_VERIFICATION` | 25+ mile verification form |
| `OTHER` | Other supporting doc |

**Upload fields:** `claim`, `document_type`, `file`, `is_signed`, optional `service_date`, `verification_date`.

---

## 13. EDI operations (837P, 999, 277, 835)

### 13.1 Outbound 837P

1. Batch ready (all claims validated)
2. `POST /edi-files/generate-837p/`
3. `POST /edi-files/{id}/upload/` (requires Celery worker + SFTP credentials)
4. Monitor `GET /edi-file-transfer-logs/`

### 13.2 Inbound 999

- **Manual:** `POST /edi-acknowledgements/import-999/` with X12 body
- **Automated:** Celery beat polls SFTP; or trigger `POST /edi-999-imports/poll/`

### 13.3 Inbound 277

- `POST /edi-acknowledgements/import-277/`
- `POST /edi-277-imports/poll/`

### 13.4 Inbound 835

- `POST /edi-835-remittances/import/`
- `POST /edi-835-imports/poll/`
- Idempotent on content SHA-256 hash

---

## 14. Document upload and download

### 14.1 Upload (multipart)

```http
POST /api/v1/claim-documents/upload/
Authorization: Bearer <token>
Content-Type: multipart/form-data

claim=1
document_type=MILE_25_VERIFICATION
file=<binary>
is_signed=true
service_date=2026-08-30
verification_date=2026-08-30
```

**Limits:** `CLAIM_DOCUMENT_MAX_BYTES` (default 10 MB). See `.env.example`.

**Response:**

```json
{
  "success": true,
  "message": "Claim document uploaded successfully.",
  "data": { "id": 5 }
}
```

### 14.2 Download

```http
GET /api/v1/claim-documents/5/file/
Authorization: Bearer <token>
```

Returns file bytes with `Content-Disposition` attachment header.

---

## 15. Security rules for integrators

1. **HTTPS only** in production
2. **Never** put JWT or SFTP passwords in the browser
3. **Never** generate 837P in RedArt frontend
4. Use **`external_id`** on claims for reconciliation
5. Use **TEST** environment until HCPF sign-off
6. Rotate service password: `create_api_service_user --rotate-password`
7. Hard delete requires **staff** Django user

---

## 16. Swagger and OpenAPI

| URL | Format |
|-----|--------|
| `/api/docs/` | Interactive Swagger UI |
| `/api/schema/` | OpenAPI 3 JSON |

Swagger is the **authoritative** list of request/response schemas when this guide and code diverge.

---

## 17. Related documents

| Document | Purpose |
|----------|---------|
| [`REDART_API_SAMPLES.md`](REDART_API_SAMPLES.md) | Copy-paste curl examples |
| [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) | Deploy to Docker / Render / production |
| [`HANDOFF.md`](HANDOFF.md) | Developer agent context |
| [`PROGRESS_REPORT.md`](PROGRESS_REPORT.md) | Done vs remaining checklist |
| [`LOVABLE_QUICKSTART.md`](LOVABLE_QUICKSTART.md) | Lovable integration quickstart |
| `RedArt_EDI_API_Integration_Handoff.pdf` | Integration contract (PDF) |
| `RedArt_52Plus_NEMT_Attachment_Workflow_Developer_Guide.pdf` | Attachment workflow (PDF) |

---

**Support:** For integration issues, check Swagger + server logs (`docker compose logs backend`). For HCPF channel questions, contact Colorado Medicaid EDI support per the attachment workflow PDF §10.
