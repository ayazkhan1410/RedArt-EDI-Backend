# Lovable + RedArt EDI API — deploy / connect handoff

## Important: Lovable does **not** host this EDI API

| Layer | Who hosts it | Role |
|--------|----------------|------|
| RedArt UI | **Lovable** (easy) | Screens only |
| RedArt backend | RedArt’s server | Calls EDI with JWT |
| **EDI API (this repo)** | **Render / Railway / Docker VPS** | 837P, SFTP, 999/835 |

Lovable can “easily” ship the **UI**. This service needs **Postgres + Redis + Celery + SFTP keys** — deploy it as a Docker API, then point RedArt (or Lovable secrets for TEST demos) at the public URL.

Correct flow:

`Lovable UI → RedArt backend → EDI API (/api/v1) → HCPF`

Do **not** put `redart_api` password or long-lived JWTs in Lovable client code for production.

---

## 1) Deploy EDI TEST API (public URL)

Recommended: [Render](https://render.com) Blueprint (`render.yaml` in repo root).

1. Push `Ayaz/local-main` to GitHub (already done).
2. Render → New → Blueprint → select this repo → apply `render.yaml`.
3. Set secrets in Render dashboard:
   - `DJANGO_SECRET_KEY` (long random)
   - `DJANGO_ALLOWED_HOSTS` = your Render hostname (e.g. `redart-edi-test.onrender.com`)
   - `CORS_ALLOWED_ORIGINS` = RedArt backend origin(s); optional Lovable preview URL
   - `EDI_ALLOW_LOVABLE_ORIGINS=true` only if browser TEST calls are required
   - `EDI_PUBLIC_BASE_URL=https://<your-render-host>`
   - `EDI_API_SERVICE_USERNAME` / `EDI_API_SERVICE_PASSWORD` (or create after deploy)
   - SFTP / MinIO vars as needed for real HCPF tests
4. After deploy, health check: `GET https://<host>/api/health/`
5. Swagger: `https://<host>/api/docs/`

Alternatives: Railway, Fly.io, or any VPS running `docker compose` with production settings.

---

## 2) Secure credential delivery (for Wahab / RedArt)

On the deployed box (or local Docker pointing at that DB):

```bash
python manage.py deliver_redart_handoff --create-user
# or:
docker compose exec backend python manage.py deliver_redart_handoff --create-user
```

Copy the printed block into **1Password / Signal** (not Slack forever, not git).

Token:

```http
POST https://<EDI_PUBLIC_BASE_URL>/api/v1/auth/token/
{"username":"redart_api","password":"<from handoff>"}
```

Samples: `docs/REDART_API_SAMPLES.md`

---

## 3) What to tell Lovable / RedArt

- **EDI base URL:** value of `EDI_PUBLIC_BASE_URL`
- **Auth:** server-side token obtain + `Authorization: Bearer …`
- **Optional Lovable secret (TEST only):** `VITE_EDI_API_BASE_URL` = same base URL  
  Prefer proxying through RedArt backend so secrets stay server-side.

---

## 4) CORS checklist

| Env | Purpose |
|-----|---------|
| `CORS_ALLOWED_ORIGINS` | Exact origins (RedArt admin, custom domains) |
| `EDI_ALLOW_LOVABLE_ORIGINS=true` | Allow `*.lovable.app` / `*.lovableproject.com` |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origins if using session/CSRF |

JWT APIs use `Authorization` header — primary path for RedArt backend.
