"""Docker Compose settings (local-like, Postgres + Redis)."""

from redartdigital.settings.local import *  # noqa: F401, F403
from redartdigital.settings.base import REST_FRAMEWORK, env

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "backend"],
)

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://127.0.0.1:7000",
        "http://localhost:7000",
    ],
)

# Terminate TLS at a reverse proxy in real deployments.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)

# Inside Compose, MinIO is reachable by service name.
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="http://minio:9000")

# Docker defaults to authenticated APIs (RedArt JWT). Opt out only for demos.
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)
if env.bool("API_REQUIRE_AUTH", default=True):
    REST_FRAMEWORK = {
        **REST_FRAMEWORK,
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.IsAuthenticated",
        ],
        "DEFAULT_THROTTLE_CLASSES": [
            "rest_framework.throttling.UserRateThrottle",
            "rest_framework.throttling.AnonRateThrottle",
        ],
        "DEFAULT_THROTTLE_RATES": {
            **(REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES") or {}),
            "user": env("API_USER_THROTTLE", default="120/min"),
            "anon": env("API_ANON_THROTTLE", default="30/min"),
            "auth_burst": env("API_AUTH_THROTTLE", default="20/min"),
        },
    }
else:
    REST_FRAMEWORK = {
        **REST_FRAMEWORK,
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.AllowAny",
        ],
    }
