# Deploy notes (ops)

Use with `docs/LOVABLE_QUICKSTART.md` (primary for Lovable).

## Public TEST URL

1. Deploy this repo (Docker / Render Blueprint `render.yaml` / Railway / VPS).
2. Set `EDI_PUBLIC_BASE_URL=https://<your-host>` (no trailing slash).
3. Set `DJANGO_ALLOWED_HOSTS`, `DJANGO_SECRET_KEY`, DB/Redis, and optionally:
   - `EDI_ALLOW_LOVABLE_ORIGINS=true`
   - `CORS_ALLOWED_ORIGINS=https://your-app.lovable.app`
4. Create credentials:
   ```bash
   python manage.py deliver_redart_handoff --create-user
   ```
5. Confirm:
   - `GET {BASE}/api/health/`
   - `GET {BASE}/api/v1/integration/lovable/`
   - `GET {BASE}/api/docs/`

Hand the base URL + username/password to RedArt/Lovable via a secure channel.
