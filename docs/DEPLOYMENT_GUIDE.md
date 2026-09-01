# RedArt EDI Backend — Deployment Guide

**Audience:** DevOps, platform engineers, and developers deploying TEST or PRODUCTION  
**Repo:** https://github.com/ayazkhan1410/RedArt-EDI-Backend  
**Branch:** `Ayaz/local-main`

This guide covers local Docker, cloud deployment (Render Blueprint), production environment variables, post-deploy verification, and handoff to RedArt integration.

For API usage after deploy, see [`API_USER_GUIDE.md`](API_USER_GUIDE.md).

---

## Table of contents

1. [Deployment overview](#1-deployment-overview)
2. [Prerequisites](#2-prerequisites)
3. [Local development (Docker Compose)](#3-local-development-docker-compose)
4. [Environment variables reference](#4-environment-variables-reference)
5. [Deploy to Render (recommended TEST)](#5-deploy-to-render-recommended-test)
6. [Deploy to any Docker host (VPS / Railway)](#6-deploy-to-any-docker-host-vps--railway)
7. [Post-deploy checklist](#7-post-deploy-checklist)
8. [Create API service user and handoff](#8-create-api-service-user-and-handoff)
9. [Database migrations](#9-database-migrations)
10. [Celery worker and Beat](#10-celery-worker-and-beat)
11. [SFTP / MFT configuration](#11-sftp--mft-configuration)
12. [Object storage (S3 / MinIO)](#12-object-storage-s3--minio)
13. [Production attachment mode](#13-production-attachment-mode)
14. [Health checks and monitoring](#14-health-checks-and-monitoring)
15. [Troubleshooting](#15-troubleshooting)
16. [Security checklist (production)](#16-security-checklist-production)

---

## 1. Deployment overview

| Component | Purpose |
|-----------|---------|
| **Web** (`backend`) | Django + Gunicorn — REST API |
| **PostgreSQL** | Primary database |
| **Redis** | Celery broker + results |
| **Celery worker** | 837P upload, SFTP poll (999/277/835) |
| **Celery beat** | Scheduled SFTP polls |
| **MinIO** (local only) | S3-compatible document storage |
| **Flower** (optional) | Celery monitoring UI |

**Architecture after deploy:**

```
RedArt backend  →  HTTPS  →  redart-edi-api  →  Postgres / Redis
                                    ↓
                              Celery worker  →  HCPF SFTP/MFT
```

---

## 2. Prerequisites

- **Git** and this repository cloned
- **Docker** + **Docker Compose** (local) or a platform that runs the repo `Dockerfile`
- **PostgreSQL 16+** and **Redis 7+** (managed or self-hosted for production)
- **S3-compatible storage** (AWS S3, MinIO, or Render-compatible object store) for claim documents
- **HCPF TEST SFTP credentials** (when testing live EDI round-trip)
- **TLS certificate** / HTTPS termination (Render and most PaaS provide this)

---

## 3. Local development (Docker Compose)

### 3.1 Clone and configure

```bash
git clone https://github.com/ayazkhan1410/RedArt-EDI-Backend.git
cd RedArt-EDI-Backend
git checkout Ayaz/local-main
cp .env.example .env
```

Edit `.env` if needed. Defaults work for local Docker.

### 3.2 Start services

```bash
docker compose up -d --build
```

First start runs migrations automatically (`RUN_MIGRATE_ON_START=true`).

### 3.3 Default ports

| Service | Host port | URL |
|---------|-----------|-----|
| API | 7000 | http://127.0.0.1:7000 |
| Postgres | 7001 | `127.0.0.1:7001` |
| Redis | 7002 | `127.0.0.1:7002` |
| Flower | 7003 | http://127.0.0.1:7003 |
| MinIO API | 7004 | http://127.0.0.1:7004 |
| MinIO console | 7005 | http://127.0.0.1:7005 |

### 3.4 Verify local deploy

```bash
curl -s http://127.0.0.1:7000/api/health/
# {"status":"ok"} or similar

curl -s http://127.0.0.1:7000/api/docs/
# Swagger HTML
```

### 3.5 Run tests

```bash
docker compose exec backend python manage.py test apps
```

### 3.6 Run migrations manually (if needed)

```bash
docker compose exec backend python manage.py migrate
```

Or from host against Docker Postgres:

```bash
set DJANGO_SETTINGS_MODULE=redartdigital.settings.local
set POSTGRES_HOST=127.0.0.1
set POSTGRES_PORT=7001
set POSTGRES_DB=edi
set POSTGRES_USER=edi
set POSTGRES_PASSWORD=edi
set POSTGRES_SSLMODE=disable
python manage.py migrate
```

### 3.7 Stop / reset

```bash
docker compose down          # stop containers
docker compose down -v       # stop + delete volumes (wipes DB)
```

---

## 4. Environment variables reference

Copy from `.env.example`. **Never commit real secrets.**

### 4.1 Required — all environments

| Variable | Description |
|----------|-------------|
| `DJANGO_SETTINGS_MODULE` | `redartdigital.settings.docker` (Compose) or `.production` (cloud) |
| `DJANGO_SECRET_KEY` | Long random string (required in production) |
| `POSTGRES_*` | DB host, port, name, user, password |
| `CELERY_BROKER_URL` | Redis URL |
| `CELERY_RESULT_BACKEND` | Redis URL (can match broker, different DB index) |

### 4.2 Required — production only

| Variable | Description |
|----------|-------------|
| `DJANGO_ALLOWED_HOSTS` | Comma-separated API hostnames |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` |
| `CSRF_TRUSTED_ORIGINS` | `https://your-api-host` |
| `CORS_ALLOWED_ORIGINS` | RedArt backend origin(s) |
| `EDI_PUBLIC_BASE_URL` | Public API URL (no trailing slash) |
| `EDI_SFTP_REQUIRE_HOST_FINGERPRINT` | `true` |
| `EDI_API_SERVICE_PASSWORD` | Strong service user password |
| `FLOWER_BASIC_AUTH` | `user:password` if Flower is exposed |

### 4.3 S3 / MinIO

| Variable | Local Docker | Production |
|----------|--------------|------------|
| `AWS_ACCESS_KEY_ID` | `minioadmin` | IAM / access key |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | Secret key |
| `AWS_STORAGE_BUCKET_NAME` | `edi-files` | Your bucket |
| `AWS_S3_ENDPOINT_URL` | `http://minio:9000` | S3 endpoint or omit for AWS |
| `AWS_S3_REGION_NAME` | `us-east-1` | Your region |

### 4.4 API auth

| Variable | Default | Description |
|----------|---------|-------------|
| `API_REQUIRE_AUTH` | `true` | Require JWT on business APIs |
| `EDI_API_SERVICE_USERNAME` | `redart_api` | Service account name |
| `EDI_API_SERVICE_EMAIL` | optional | Email for service user |
| `JWT_ACCESS_MINUTES` | 60 | Access token lifetime |
| `JWT_REFRESH_DAYS` | 7 | Refresh token lifetime |

### 4.5 Attachment production (when HCPF confirms channel)

```env
ATTACHMENT_PRODUCTION_MODE=true
ATTACHMENT_PRODUCTION_DEFAULT_CHANNEL=HCPF_APPROVED_CHANNEL
ATTACHMENT_MFT_ENABLED=true
ATTACHMENT_MFT_ENVIRONMENT=PRODUCTION
ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE={claim_number}/{document_type}/{filename}
```

### 4.6 EDI / SFTP

| Variable | Description |
|----------|-------------|
| `EDI_DEFAULT_BILLING_TAX_ID` | Provider TIN for 837P REF*EI if not on profile |
| `EDI_MAX_SFTP_DOWNLOAD_BYTES` | Max inbound file size (default 5 MB) |
| `EDI_MAX_X12_CONTENT_CHARS` | Max paste-import size (default 2 MB) |
| `EDI_SFTP_REQUIRE_HOST_FINGERPRINT` | SSH host-key verification |
| `SFTP_SEED_*` | Optional seed credentials on first boot |

---

## 5. Deploy to Render (recommended TEST)

The repo includes `render.yaml` Blueprint.

### 5.1 Steps

1. Push `Ayaz/local-main` to GitHub (already done if you pulled latest).
2. In [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**.
3. Connect repo `ayazkhan1410/RedArt-EDI-Backend`.
4. Render provisions:
   - `edi-postgres` (PostgreSQL)
   - `edi-redis` (Redis)
   - `redart-edi-api` (web service, Docker `web` command)
   - `redart-edi-worker` (Celery worker)
5. Set **manual env vars** in Render UI (marked `sync: false` in blueprint):

| Variable | Example |
|----------|---------|
| `DJANGO_ALLOWED_HOSTS` | `redart-edi-api.onrender.com` |
| `EDI_PUBLIC_BASE_URL` | `https://redart-edi-api.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://your-redart-backend.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://redart-edi-api.onrender.com` |
| `EDI_API_SERVICE_PASSWORD` | (strong generated password) |
| `AWS_*` | S3 credentials if using external object storage |

6. Wait for deploy. Health check: `/api/health/`.

### 5.2 Render limitations (free tier)

- Web service may sleep on inactivity — use paid plan for always-on TEST.
- Worker must run separately (blueprint includes `redart-edi-worker`).
- Configure **object storage** — Render free tier does not include MinIO; use AWS S3 or compatible service.

### 5.3 Add Celery Beat on Render (optional)

If not in blueprint, add a **Background Worker** with `dockerCommand: beat` and same env as worker.

---

## 6. Deploy to any Docker host (VPS / Railway)

### 6.1 Build image

```bash
docker build -t redart-edi:latest .
```

### 6.2 Run web

```bash
docker run -d --name redart-api \
  -p 8000:8000 \
  -e DJANGO_SETTINGS_MODULE=redartdigital.settings.production \
  -e USE_GUNICORN=true \
  -e RUN_MIGRATE_ON_START=true \
  -e DJANGO_SECRET_KEY=<secret> \
  -e DJANGO_ALLOWED_HOSTS=api.example.com \
  -e POSTGRES_HOST=<db-host> \
  -e POSTGRES_PASSWORD=<db-password> \
  -e CELERY_BROKER_URL=redis://<redis>:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://<redis>:6379/1 \
  redart-edi:latest web
```

### 6.3 Run worker

```bash
docker run -d --name redart-worker \
  -e DJANGO_SETTINGS_MODULE=redartdigital.settings.production \
  ... (same DB/Redis env) \
  redart-edi:latest worker
```

### 6.4 Run beat

```bash
docker run -d --name redart-beat \
  ... \
  redart-edi:latest beat
```

### 6.5 Reverse proxy

Put **nginx**, **Caddy**, or cloud load balancer in front with TLS. Forward `X-Forwarded-Proto: https` — production settings enable `SECURE_PROXY_SSL_HEADER`.

---

## 7. Post-deploy checklist

Run these in order after every new environment:

| # | Check | Command / URL |
|---|-------|---------------|
| 1 | Health | `GET https://<host>/api/health/` → 200 |
| 2 | Swagger | `GET https://<host>/api/docs/` → loads |
| 3 | OpenAPI | `GET https://<host>/api/schema/` → JSON |
| 4 | Lovable catalog | `GET https://<host>/api/v1/integration/lovable/` |
| 5 | Auth | `POST https://<host>/api/v1/auth/token/` with service credentials → 200 + tokens |
| 6 | Protected API | `GET https://<host>/api/v1/patients/` without token → 401 |
| 7 | Migrations | No errors in web container logs on startup |
| 8 | Worker | Celery worker container running; upload task succeeds |
| 9 | S3 | Document upload returns 201 |
| 10 | Public URL | `EDI_PUBLIC_BASE_URL` matches actual HTTPS base |

---

## 8. Create API service user and handoff

### Option A — management command (recommended)

```bash
# Docker local
docker compose exec backend python manage.py deliver_redart_handoff --create-user

# Or create/rotate only
docker compose exec backend python manage.py create_api_service_user \
  --username redart_api \
  --generate-password
```

### Option B — environment on first boot

Set in production env:

```env
EDI_API_SERVICE_USERNAME=redart_api
EDI_API_SERVICE_PASSWORD=<strong-password>
```

Entrypoint can create the user when configured.

### Handoff package for RedArt / Wahab

Deliver **securely** (password manager, encrypted channel — not email/plain Slack):

1. **TEST API base URL** — `https://<host>` (no trailing slash)
2. **Username** — `redart_api`
3. **Password** — service user password
4. **Swagger URL** — `https://<host>/api/docs/`
5. **Sample doc** — link to `docs/REDART_API_SAMPLES.md` in repo
6. **Integration catalog** — `GET /api/v1/integration/lovable/`

### Test token from deploy

```bash
curl -s -X POST "https://<host>/api/v1/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"redart_api","password":"<password>"}'
```

---

## 9. Database migrations

Migrations run automatically when `RUN_MIGRATE_ON_START=true` (Docker entrypoint).

**Manual migrate:**

```bash
docker compose exec backend python manage.py migrate
# or on Render shell:
python manage.py migrate
```

**After pulling new code with model changes:**

1. Pull latest `Ayaz/local-main`
2. Redeploy or restart containers
3. Confirm migrate in logs
4. Run tests

**Never** run `makemigrations` on production without reviewing migration files in dev first.

---

## 10. Celery worker and Beat

| Service | Compose | Render blueprint | Command |
|---------|---------|------------------|---------|
| Worker | `celery-worker` | `redart-edi-worker` | `worker` |
| Beat | `celery-beat` | add manually if needed | `beat` |

**Scheduled tasks (Beat):**

- 999 SFTP poll (hourly)
- 835 SFTP poll (hourly offset)
- 277 SFTP poll (if configured)

**837P upload** is triggered by API `POST /edi-files/{id}/upload/` — requires worker running.

**Verify worker:**

```bash
docker compose logs celery-worker --tail 50
```

**Flower (local monitoring):**

- URL: http://127.0.0.1:7003
- Set `FLOWER_BASIC_AUTH=user:password` in `.env` (required — no default weak password)

---

## 11. SFTP / MFT configuration

Configure via API after deploy (or seed via env `SFTP_SEED_*`).

### 11.1 Create credentials

```http
POST /api/v1/sftp-credentials/
Authorization: Bearer <token>

{
  "name": "HCPF TEST MFT",
  "environment": "TEST",
  "host": "mft.example.hcpf.gov",
  "port": 22,
  "username": "redart_test",
  "auth_type": "PASSWORD",
  "password": "<secret>",
  "host_fingerprint": "SHA256:..."
}
```

Passwords are **encrypted at rest**. GET responses never return the password.

### 11.2 Create directories

```http
POST /api/v1/sftp-directories/

{
  "credentials": 1,
  "purpose": "OUTBOUND_837P",
  "sending_path": "/outbound/837p",
  "receiving_path": "/inbound/999",
  "environment": "TEST"
}
```

**Purposes:** `OUTBOUND_837P`, `INBOUND_999`, `INBOUND_835`, `INBOUND_277`, `OUTBOUND_ATTACHMENT`, `GENERAL`.

### 11.3 Production host-key policy

Set `EDI_SFTP_REQUIRE_HOST_FINGERPRINT=true` and provide `host_fingerprint` on each credential.

---

## 12. Object storage (S3 / MinIO)

**Local:** MinIO starts with Compose. Bucket `edi-files` is created by entrypoint.

**Production:** Use AWS S3 or compatible storage. Set `AWS_*` env vars. Ensure bucket exists and credentials have read/write.

**Test upload after deploy:**

```bash
curl -s -X POST "https://<host>/api/v1/claim-documents/upload/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "claim=1" \
  -F "document_type=STANDARD_TRIP_LOG" \
  -F "file=@trip-log.pdf" \
  -F "is_signed=true"
```

---

## 13. Production attachment mode

Only enable after **HCPF confirms** the attachment channel (see Attachment Workflow PDF §6–7).

```env
ATTACHMENT_PRODUCTION_MODE=true
ATTACHMENT_MFT_ENABLED=true
ATTACHMENT_PRODUCTION_DEFAULT_CHANNEL=HCPF_APPROVED_CHANNEL
ATTACHMENT_MFT_ENVIRONMENT=PRODUCTION
ATTACHMENT_MFT_REMOTE_PATH_TEMPLATE={claim_number}/{document_type}/{filename}
```

Create `OUTBOUND_ATTACHMENT` SFTP directory pointing to HCPF’s attachment path.

Test with:

```http
POST /api/v1/attachment-submissions/submit/
{ "claim_id": 1, "channel": "HCPF_APPROVED_CHANNEL" }
```

---

## 14. Health checks and monitoring

| Endpoint | Auth | Use |
|----------|------|-----|
| `GET /api/health/` | No | Load balancer / Render health |
| `GET /api/docs/` | No | Smoke test |
| Django admin `/admin/` | Staff login | Ops |
| Flower `:7003` | Basic auth | Celery queue depth |

**Logs:**

```bash
docker compose logs backend -f
docker compose logs celery-worker -f
```

**Key log lines:** migration success, Gunicorn start, Celery task `upload_edi_file`, SFTP poll results.

---

## 15. Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| `401` on all APIs | Missing/invalid JWT | Obtain token; check `API_REQUIRE_AUTH` |
| `failed to resolve host 'db'` | Running migrate on host with Docker `.env` | Use `POSTGRES_HOST=127.0.0.1` and port `7001` |
| Upload stays queued | Celery worker not running | Start `celery-worker` service |
| SFTP upload fails | Wrong credentials / fingerprint | Check `edi-file-transfer-logs`; set fingerprint |
| 837P generate 400 | Claim not ready | `POST /claims/{id}/validate/`; fix errors |
| Document upload 413 | File too large | Increase `CLAIM_DOCUMENT_MAX_BYTES` |
| CORS errors from Lovable | Origin not allowed | Set `CORS_ALLOWED_ORIGINS` or `EDI_ALLOW_LOVABLE_ORIGINS=true` |
| Flower won't start | `FLOWER_BASIC_AUTH` empty | Set `user:password` in env |
| Migrations fail on deploy | Old DB state | Check migration logs; restore from backup before force |

---

## 16. Security checklist (production)

- [ ] `DJANGO_DEBUG=false`
- [ ] Strong `DJANGO_SECRET_KEY` (unique per environment)
- [ ] `DJANGO_ALLOWED_HOSTS` set to actual hostname only
- [ ] HTTPS enforced (`DJANGO_SECURE_SSL_REDIRECT=true`)
- [ ] `API_REQUIRE_AUTH=true`
- [ ] `CORS_ALLOW_ALL_ORIGINS=false`; explicit `CORS_ALLOWED_ORIGINS`
- [ ] `EDI_SFTP_REQUIRE_HOST_FINGERPRINT=true`
- [ ] SFTP secrets only via API/admin; never in git
- [ ] Service user password rotated; not shared in chat
- [ ] `FLOWER_BASIC_AUTH` set if Flower is exposed
- [ ] Postgres and Redis not publicly exposed without auth
- [ ] S3 bucket private; presigned or API-only access
- [ ] `.env` in `.gitignore`; secrets in platform secret store

---

## Quick reference — deploy commands

```bash
# Local full stack
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py create_api_service_user --username redart_api --generate-password
docker compose exec backend python manage.py test apps

# Handoff bundle
docker compose exec backend python manage.py deliver_redart_handoff --create-user
```

---

**Next:** Share TEST URL + credentials with RedArt, then run live HCPF TEST (837P → 999 → Edifecs reports). See [`PROGRESS_REPORT.md`](PROGRESS_REPORT.md) for remaining ops items.
