"""Docker Compose settings (local-like, Postgres + Redis)."""

from redartdigital.settings.local import *  # noqa: F401, F403
from redartdigital.settings.base import env

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "web"],
)

# Terminate TLS at a reverse proxy in real deployments.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
