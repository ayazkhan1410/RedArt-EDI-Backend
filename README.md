# RedArt EDI Backend

Django REST microservice for **Colorado Medicaid NEMT** — HIPAA **X12 837P** generation, batching, SFTP/MFT transport, acknowledgements (999/277), remittance (835), and long-distance attachment workflow.

**Architecture:** RedArt UI → RedArt backend → **this API** (`/api/v1/`) → HCPF (SFTP/MFT).  
This repo is the **EDI backend only** — not the RedArt frontend or RedArt's main application.

| Resource | Location |
|----------|----------|
| **API user guide (start here)** | [`docs/API_USER_GUIDE.md`](docs/API_USER_GUIDE.md) |
| **Deployment guide** | [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) |
| **Cursor / dev quick-start** | [`cursor.md`](cursor.md) |
| Integration samples | `docs/REDART_API_SAMPLES.md` |
| Agent / dev context | `docs/HANDOFF.md` |
| Integration architecture (FigJam) | https://www.figma.com/board/qM4zo4vMIAJioyLQsetRkm |
| Backend status diagram (FigJam) | https://www.figma.com/board/BON1SRPbQOvxHhDWFnDpr8 |

**Branch:** `Ayaz/local-main` · **Repo:** https://github.com/ayazkhan1410/RedArt-EDI-Backend

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
| http://127.0.0.1:7000/api/health/ | Health check |
| http://127.0.0.1:7000/api/docs/ | Swagger / OpenAPI |
| http://127.0.0.1:7000/admin/ | Django admin |

See **`.env.example`** for all required environment variables.

## Key integration endpoints

| Step | Endpoint |
|------|----------|
| Auth | `POST /api/v1/auth/token/` |
| Sync provider | `POST /api/v1/provider-billing-profiles/` |
| Sync patient | `POST /api/v1/patients/` |
| Create trip | `POST /api/v1/nemt-trips/` |
| Create claim | `POST /api/v1/claims/` |
| Upload document | `POST /api/v1/claim-documents/upload/` |
| Validate claim | `POST /api/v1/claims/{id}/validate/` |
| Claim status | `GET /api/v1/claims/{id}/status/` |
| Create batch | `POST /api/v1/submission-batches/` |
| Generate 837P | `POST /api/v1/edi-files/generate-837p/` |
| Import 999 | `POST /api/v1/edi-acknowledgements/import-999/` |
| Poll 999 SFTP | `POST /api/v1/edi-999-imports/poll/` |
| Import 277 | `POST /api/v1/edi-acknowledgements/import-277/` |
| Import 835 | `POST /api/v1/edi-835-imports/import/` |
| Attachment queue | `GET /api/v1/claims/attachment-queue/` |
| Submit attachments | `POST /api/v1/attachment-submissions/submit/` |
| Long-distance pilot | `POST /api/v1/pilot/long-distance/` |

Full reference: `docs/API_USER_GUIDE.md` · Samples: `docs/REDART_API_SAMPLES.md`

## Claim status lifecycle

```
DRAFT → READY_FOR_837P → EDI_GENERATED → EDI_SENT → EDI_ACCEPTED → PAID
                                                  ↘ EDI_REJECTED (fix + resubmit)
```

| Status | Meaning |
|--------|---------|
| `DRAFT` | Created, data entry in progress |
| `DOCUMENTS_REQUIRED` | Long-distance — docs needed |
| `DOCUMENTS_COMPLETE` | All required docs present |
| `READY_FOR_837P` | Passed validation |
| `EDI_GENERATED` | 837P file built (not yet uploaded) |
| `EDI_SENT` | 837P uploaded to HCPF SFTP/MFT |
| `EDI_ACCEPTED` | 999/TA1 accepted |
| `EDI_REJECTED` | 999/TA1 rejected — needs correction |
| `UNDER_REVIEW` | Adjudicating at payer |
| `PAID` | Payment received |
| `DENIED` | Denied by payer |

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

229 tests covering 837P generation, atypical providers, multi-company isolation,
acknowledgements, 835 remittance, auth, and enterprise edge cases.

## License

Proprietary — RedArt LLC. All rights reserved.
