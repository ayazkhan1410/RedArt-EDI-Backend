# Lovable quickstart — RedArt EDI APIs

Simple guide for wiring this EDI backend from Lovable / RedArt.

## Secrets (Cloud tab)

| Secret | Example | Required |
|--------|---------|----------|
| `VITE_EDI_API_BASE_URL` | `https://your-edi-host` (no trailing slash) | Yes |
| `EDI_SERVICE_USERNAME` | `redart_api` | Yes (server/proxy) |
| `EDI_SERVICE_PASSWORD` | *(from ops)* | Yes (server/proxy) |

Local Docker default base: `http://127.0.0.1:7000`

Live docs while API is up: `{BASE}/api/docs/`  
Machine catalog: `GET {BASE}/api/v1/integration/lovable/`

---

## Auth (do this first)

```http
POST {BASE}/api/v1/auth/token/
Content-Type: application/json

{"username":"redart_api","password":"<password>"}
```

Response:

```json
{"access":"<jwt>","refresh":"<jwt>","token_type":"Bearer","expires_in":3600}
```

Every business call:

```http
Authorization: Bearer <access>
```

Refresh: `POST {BASE}/api/v1/auth/token/refresh/` with `{"refresh":"..."}`.

---

## Happy path (order matters)

1. Create patient → `POST /api/v1/patients/`
2. Create provider → `POST /api/v1/provider-billing-profiles/`
3. Create trip → `POST /api/v1/nemt-trips/`
4. Create claim → `POST /api/v1/claims/from-trip/`
5. Validate → `POST /api/v1/claims/{id}/validate/` → `{ ready, errors[] }`
6. Status → `GET /api/v1/claims/{id}/status/`
7. Batch → `POST /api/v1/submission-batches/` + `.../add-claim/`
8. Generate 837P → `POST /api/v1/edi-files/generate-837p/`
9. Upload → `POST /api/v1/edi-files/{id}/upload/`
10. 999 (optional) → `POST /api/v1/edi-acknowledgements/import-999/`
11. 835 paid/denied → `POST /api/v1/edi-835-remittances/import/`

Write responses return `{ "success", "message", "data": { "id": ... } }` unless noted.

Full curl pack: `docs/REDART_API_SAMPLES.md`

---

## TypeScript helper (paste into Lovable)

```ts
const BASE = import.meta.env.VITE_EDI_API_BASE_URL?.replace(/\/$/, "") ?? "";

export async function ediToken(username: string, password: string) {
  const res = await fetch(`${BASE}/api/v1/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(`token failed: ${res.status}`);
  return res.json() as Promise<{ access: string; refresh: string; expires_in: number }>;
}

export async function ediFetch(
  path: string,
  access: string,
  init: RequestInit = {},
) {
  const url = path.startsWith("http") ? path : `${BASE}${path.startsWith("/") ? "" : "/"}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${access}`,
      ...(init.headers || {}),
    },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(body.message || res.statusText), { status: res.status, body });
  return body;
}

// Examples:
// await ediFetch("/api/v1/claims/1/validate/", token.access, { method: "POST", body: "{}" });
// await ediFetch("/api/v1/claims/1/status/", token.access);
```

---

## Checklist before go-live

- [ ] `{BASE}/api/health/` returns OK  
- [ ] Token obtain works  
- [ ] Swagger opens at `/api/docs/`  
- [ ] Validate + status work on a seed claim  
- [ ] CORS / secrets set for your Lovable preview URL if calling from browser  

Ops: `python manage.py deliver_redart_handoff --create-user`
