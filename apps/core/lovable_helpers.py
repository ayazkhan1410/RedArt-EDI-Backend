"""
Helpers + catalog for Lovable / RedArt integration.

Use from Python (RedArt backend) or expose via GET /api/v1/integration/lovable/.
"""

from __future__ import annotations

from django.conf import settings

# Stable path constants (append to EDI base URL).
AUTH_TOKEN_PATH = "/api/v1/auth/token/"
AUTH_REFRESH_PATH = "/api/v1/auth/token/refresh/"
AUTH_VERIFY_PATH = "/api/v1/auth/token/verify/"
HEALTH_PATH = "/api/health/"
SWAGGER_PATH = "/api/docs/"
INTEGRATION_CATALOG_PATH = "/api/v1/integration/lovable/"

CLAIM_VALIDATE_PATH = "/api/v1/claims/{id}/validate/"
CLAIM_STATUS_PATH = "/api/v1/claims/{id}/status/"
CLAIMS_FROM_TRIP_PATH = "/api/v1/claims/from-trip/"
BATCH_ADD_CLAIM_PATH = "/api/v1/submission-batches/{id}/add-claim/"
BATCH_STATUS_PATH = "/api/v1/submission-batches/{id}/status/"
GENERATE_837P_PATH = "/api/v1/edi-files/generate-837p/"
UPLOAD_EDI_PATH = "/api/v1/edi-files/{id}/upload/"
IMPORT_999_PATH = "/api/v1/edi-acknowledgements/import-999/"
IMPORT_835_PATH = "/api/v1/edi-835-remittances/import/"


def public_base_url() -> str:
    """Configured public API base (no trailing slash), or local Docker default."""
    base = (getattr(settings, "EDI_PUBLIC_BASE_URL", None) or "").rstrip("/")
    return base or "http://127.0.0.1:7000"


def absolute_url(path: str, *, base: str | None = None) -> str:
    root = (base or public_base_url()).rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{root}{path}"


def bearer_headers(access_token: str) -> dict[str, str]:
    """Headers for authenticated EDI calls."""
    token = (access_token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def fill_path(template: str, **ids) -> str:
    """Replace {id} style placeholders in path templates."""
    out = template
    for key, value in ids.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def lovable_env_secrets() -> list[dict]:
    return [
        {
            "name": "VITE_EDI_API_BASE_URL",
            "required": True,
            "example": public_base_url(),
            "notes": "No trailing slash. Used by Lovable/RedArt to reach this API.",
        },
        {
            "name": "EDI_SERVICE_USERNAME",
            "required": True,
            "example": "redart_api",
            "notes": "API service user for POST /api/v1/auth/token/.",
        },
        {
            "name": "EDI_SERVICE_PASSWORD",
            "required": True,
            "example": "(from deliver_redart_handoff)",
            "notes": "Keep server-side when possible; rotate with create_api_service_user.",
        },
    ]


def lovable_happy_path() -> list[dict]:
    """Ordered steps Lovable/RedArt should follow for one claim → 837P."""
    return [
        {"step": 1, "method": "POST", "path": AUTH_TOKEN_PATH, "why": "Get Bearer access token"},
        {"step": 2, "method": "POST", "path": "/api/v1/patients/", "why": "Create member"},
        {
            "step": 3,
            "method": "POST",
            "path": "/api/v1/provider-billing-profiles/",
            "why": "Create billing provider",
        },
        {"step": 4, "method": "POST", "path": "/api/v1/nemt-trips/", "why": "Create trip"},
        {
            "step": 5,
            "method": "POST",
            "path": CLAIMS_FROM_TRIP_PATH,
            "why": "Create claim from trip_id",
        },
        {
            "step": 6,
            "method": "POST",
            "path": CLAIM_VALIDATE_PATH,
            "why": "Check ready + errors before submit",
        },
        {"step": 7, "method": "GET", "path": CLAIM_STATUS_PATH, "why": "Poll claim status"},
        {
            "step": 8,
            "method": "POST",
            "path": "/api/v1/submission-batches/",
            "why": "Create batch",
        },
        {
            "step": 9,
            "method": "POST",
            "path": BATCH_ADD_CLAIM_PATH,
            "why": "Attach claim to batch",
        },
        {
            "step": 10,
            "method": "POST",
            "path": GENERATE_837P_PATH,
            "why": "Build X12 837P file",
        },
        {
            "step": 11,
            "method": "POST",
            "path": UPLOAD_EDI_PATH,
            "why": "Queue SFTP upload to HCPF",
        },
        {
            "step": 12,
            "method": "POST",
            "path": IMPORT_999_PATH,
            "why": "Optional: import 999 ack (not payment)",
        },
        {
            "step": 13,
            "method": "POST",
            "path": IMPORT_835_PATH,
            "why": "Optional: import 835 → PAID/DENIED",
        },
    ]


def build_lovable_catalog() -> dict:
    """JSON catalog for Lovable (also returned by integration API)."""
    base = public_base_url()
    return {
        "product": "RedArt EDI API",
        "version": "0.1.0",
        "base_url": base,
        "docs": {
            "swagger": absolute_url(SWAGGER_PATH, base=base),
            "quickstart": "docs/LOVABLE_QUICKSTART.md",
            "samples": "docs/REDART_API_SAMPLES.md",
        },
        "auth": {
            "type": "JWT",
            "token_url": absolute_url(AUTH_TOKEN_PATH, base=base),
            "refresh_url": absolute_url(AUTH_REFRESH_PATH, base=base),
            "header": "Authorization: Bearer <access>",
            "body": {"username": "redart_api", "password": "<service-password>"},
        },
        "health_url": absolute_url(HEALTH_PATH, base=base),
        "env_secrets": lovable_env_secrets(),
        "happy_path": lovable_happy_path(),
        "key_endpoints": {
            "health": HEALTH_PATH,
            "integration_catalog": INTEGRATION_CATALOG_PATH,
            "provider_profiles": "/api/v1/provider-billing-profiles/",
            "trading_partners": "/api/v1/trading-partners/",
            "patients": "/api/v1/patients/",
            "nemt_trips": "/api/v1/nemt-trips/",
            "claims": "/api/v1/claims/",
            "claim_from_trip": CLAIMS_FROM_TRIP_PATH,
            "submission_batches": "/api/v1/submission-batches/",
            "batch_add_claim": BATCH_ADD_CLAIM_PATH,
            "validate_claim": CLAIM_VALIDATE_PATH,
            "claim_status": CLAIM_STATUS_PATH,
            "batch_status": BATCH_STATUS_PATH,
            "generate_837p": GENERATE_837P_PATH,
            "upload_edi": UPLOAD_EDI_PATH,
            "import_999": IMPORT_999_PATH,
            "import_835": IMPORT_835_PATH,
        },
        "response_shape": {
            "writes": {"success": True, "message": "...", "data": {"id": 1}},
            "validate": {
                "success": True,
                "data": {"ready": True, "errors": [], "claim_id": 1},
            },
        },
        "typescript_hint": (
            "See docs/LOVABLE_QUICKSTART.md — ediToken() + ediFetch() helpers."
        ),
    }
