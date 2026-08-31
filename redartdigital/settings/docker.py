"""Docker Compose settings (local-like, Postgres + Redis)."""

from redartdigital.settings.local import *  # noqa: F401, F403
from redartdigital.settings.base import env

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
