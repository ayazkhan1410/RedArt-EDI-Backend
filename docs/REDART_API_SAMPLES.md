# RedArt ↔ EDI Backend — API samples (TEST)

Base URL (local Docker): `http://127.0.0.1:7000`  
After cloud deploy: set `EDI_PUBLIC_BASE_URL` (see `docs/LOVABLE_EDI_DEPLOY.md`).  
Swagger: `{BASE}/api/docs/`  
Auth: JWT Bearer from a **service user** (not the browser).

**Lovable:** start with [`docs/LOVABLE_QUICKSTART.md`](LOVABLE_QUICKSTART.md) and `GET /api/v1/integration/lovable/`.

Create service user (one-time):

```bash
docker compose exec backend python manage.py create_api_service_user \
  --username redart_api \
  --generate-password
```

Store the printed password securely. Or set env and restart:

- `EDI_API_SERVICE_USERNAME`
- `EDI_API_SERVICE_PASSWORD`
- `EDI_API_SERVICE_EMAIL` (optional)

---

## 1) Obtain token

**Request**

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "username": "redart_api",
  "password": "<service-password>"
}
```

**Response (200)**

```json
{
  "refresh": "<refresh-jwt>",
  "access": "<access-jwt>",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**curl**

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/auth/token/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"redart_api\",\"password\":\"YOUR_PASSWORD\"}"
```

Use header on all business APIs:

```http
Authorization: Bearer <access>
```

---

## 2) Happy path (RedArt → EDI)

Assume `TOKEN` is the access JWT.

### Create patient

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/patients/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"first_name\":\"JANE\",\"last_name\":\"TESTPATIENT\",\"date_of_birth\":\"1950-01-01\",\"gender\":\"F\",\"medicaid_member_id\":\"Y999999\",\"county\":\"Pueblo\",\"address_line_1\":\"100 TEST STREET\",\"city\":\"PUEBLO\",\"state\":\"CO\",\"zip\":\"81001\"}"
```

**Response shape:** `{ "success": true, "message": "...", "data": { "id": <patient_id> } }`

### Create provider billing profile

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/provider-billing-profiles/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"legal_name\":\"REDART LLC\",\"billing_name\":\"REDART LLC\",\"npi\":\"9000211959\",\"address_line_1\":\"1276 SANDALWOOD DR APT B\",\"city\":\"COLORADO SPRINGS\",\"state\":\"CO\",\"zip\":\"80918\"}"
```

### Create trip

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/nemt-trips/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"patient\":<patient_id>,\"provider\":<provider_id>,\"service_date\":\"2026-08-05\",\"pickup\":\"Home\",\"dropoff\":\"Clinic\",\"one_way_miles\":\"8.00\",\"mileage_units\":1,\"charge\":\"14.90\"}"
```

### Create claim from trip

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/claims/from-trip/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"trip_id\":<trip_id>,\"claim_number\":\"TESTCLAIM0001\",\"diagnosis_code\":\"R69\",\"place_of_service\":\"03\"}"
```

### Validate claim (handoff shape)

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/claims/<claim_id>/validate/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{}"
```

**Response (ready)**

```json
{
  "success": true,
  "message": "Claim validation complete.",
  "data": {
    "ready": true,
    "errors": [],
    "warnings": [],
    "claim_id": 1,
    "status": "READY_FOR_837P"
  }
}
```

**Response (not ready)**

```json
{
  "success": true,
  "message": "Claim validation complete.",
  "data": {
    "ready": false,
    "errors": ["Patient demographics incomplete (gender, address_line_1, city, state, zip)."],
    "claim_id": 1,
    "status": "DRAFT"
  }
}
```

### Claim status

```bash
curl -s "http://127.0.0.1:7000/api/v1/claims/<claim_id>/status/" \
  -H "Authorization: Bearer $TOKEN"
```

### Create batch + add claim + generate 837P + upload

```bash
# batch
curl -s -X POST "http://127.0.0.1:7000/api/v1/submission-batches/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"batch_number\":\"REDART-BATCH-1\",\"trading_partner\":<tp_id>,\"environment\":\"TEST\"}"

# add claim
curl -s -X POST "http://127.0.0.1:7000/api/v1/submission-batches/<batch_id>/add-claim/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"claim_id\":<claim_id>}"

# generate
curl -s -X POST "http://127.0.0.1:7000/api/v1/edi-files/generate-837p/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"batch_id\":<batch_id>}"

# upload (Celery worker must be running)
curl -s -X POST "http://127.0.0.1:7000/api/v1/edi-files/<edi_file_id>/upload/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"credentials_id\":<sftp_credentials_id>}"
```

### Batch status

```bash
curl -s "http://127.0.0.1:7000/api/v1/submission-batches/<batch_id>/status/" \
  -H "Authorization: Bearer $TOKEN"
```

### Import 835 (paid / denied)

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/edi-835-remittances/import/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"content\":\"ST*835*0001~CLP*TESTCLAIM0001*1*14.90*14.90*0*MC*X*11~\",\"apply_claim_status\":true}"
```

**CLP02 mapping (v1):** `1/2/3/19/20/21` + payment > 0 → `Claim.status=PAID`; `4` or $0 processed → `DENIED`; `22/23/25` → `UNDER_REVIEW` (won't overwrite existing PAID/DENIED). List: `GET /api/v1/edi-835-remittances/`.

### Import 999 (manual paste)

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/edi-acknowledgements/import-999/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"batch_id\":<batch_id>,\"edi_file_id\":<edi_file_id>,\"content\":\"ISA*...999...\"}"
```

Or poll SFTP:

```bash
curl -s -X POST "http://127.0.0.1:7000/api/v1/edi-999-imports/poll/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"credentials_id\":<sftp_credentials_id>,\"async_mode\":true}"
```

---

## Security notes for RedArt

- Call this API **only from RedArt’s backend** (never put JWT secrets in the browser).
- Rotate service password with `--rotate-password` / env update.
- Token obtain is **rate-limited** (`auth_burst`, default 20/min).
- Only users in group `edi_api_service` (or staff) can obtain tokens.
- Production settings require authentication on all business endpoints.
- Local/Docker may use `API_REQUIRE_AUTH=true` to enforce the same behavior.
