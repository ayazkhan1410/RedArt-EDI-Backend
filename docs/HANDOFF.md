# RedArt EDI Backend — Handoff

Use this on any machine. Open a **new** Cursor chat and say:

> Read `docs/HANDOFF.md` and `.cursor/rules/edi-project.mdc`, then continue from **Next to build**.

Branch: **`Ayaz/local-main`**  
Repo: https://github.com/ayazkhan1410/RedArt-EDI-Backend

---

## What this project is

Django/DRF microservice for **RedArt Digital** (NEMT) — Colorado Medicaid **HIPAA X12 837P** EDI engine.

- RedArt UI → RedArt backend → **this API** → HCPF
- Long-distance claims: documents + 837P + separate attachment channel
- Trading Partner ≠ Provider Billing Profile

Key PDF: `RedArt_52Plus_NEMT_Attachment_Workflow_Developer_Guide.pdf` (local, gitignored)

---

## Stack / run

- Django **5.2**, apps under `apps/`
- Docker: ports **7000** API, **7001** Postgres, **7002** Redis
- Swagger: `http://127.0.0.1:7000/api/docs/`
- Health: `GET /api/health/`

```bash
git checkout Ayaz/local-main && git pull
docker compose up -d
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=7001 POSTGRES_DB=edi POSTGRES_USER=edi POSTGRES_PASSWORD=edi POSTGRES_SSLMODE=disable \
  python manage.py migrate
```

---

## Built (backend complete for integration)

### Core EDI
- Trips, claims, batches, service lines, 837P generate/upload
- 999 import (paste + SFTP poll)
- 277 import (paste + SFTP poll)
- 835 remittance import + SFTP poll
- Edifecs validation reports (audit/LDNS XML)
- JWT auth + API service user

### Attachment workflow
- Document upload/download (S3/MinIO + local fallback)
- `service_date` + `verification_date` on claim documents
- Attachment queue + dashboard
- Portal + **production MFT** adapters
- `POST /attachment-submissions/submit/`
- `POST /attachment-submissions/bulk-review/` (SUBMIT / CONFIRM / FAIL)
- Long-distance pilot: `POST /pilot/long-distance/`

### Useful endpoints
- `/api/v1/claim-documents/upload/`
- `/api/v1/claims/attachment-queue/`
- `/api/v1/claims/attachment-dashboard/`
- `/api/v1/pilot/long-distance/`
- `/api/v1/edi-acknowledgements/import-999/`
- `/api/v1/edi-999-imports/poll/`
- `/api/v1/edi-acknowledgements/import-277/`
- `/api/v1/edi-277-imports/poll/`
- `/api/v1/edi-validation-reports/import/`

---

## Production attachment env vars

```env
ATTACHMENT_MFT_ENABLED=true
ATTACHMENT_PRODUCTION_MODE=true
ATTACHMENT_PRODUCTION_DEFAULT_CHANNEL=HCPF_APPROVED_CHANNEL
ATTACHMENT_MFT_ENVIRONMENT=PRODUCTION
ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE={claim_number}/{document_type}/{filename}
```

Requires active `OUTBOUND_ATTACHMENT` SFTP directory for the target environment.

---

## Next to build (ops only)

1. Deploy TEST API URL (Render) + hand off URL/token to Wahab
2. Live HCPF TEST: upload 837P → confirm 999 + Edifecs XML
3. Client confirmation of attachment channel (if different from MFT)
4. Run long-distance pilot with real signed documents on TEST

Patient demographics and `EDI_ENVELOPE` settings are in place.  
Use `assert_batch_ready_for_837p_generation` before generate.

---

## Ubuntu laptop checklist

1. Clone/pull `Ayaz/local-main`
2. Copy `.env` (never commit secrets)
3. `docker compose up -d`
4. `python manage.py migrate` against Postgres on port 7001
