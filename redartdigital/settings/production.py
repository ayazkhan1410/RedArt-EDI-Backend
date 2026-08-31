"""Production settings. Requires environment variables — no insecure defaults."""

from redartdigital.settings.base import *  # noqa: F401, F403
from redartdigital.settings.base import REST_FRAMEWORK, env

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production.")

# TLS terminates at the reverse proxy / load balancer (Render, nginx, ALB).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_SSL_REDIRECT = env("DJANGO_SECURE_SSL_REDIRECT")
# Allow plain-HTTP health probes against the container (proxy still uses HTTPS).
SECURE_REDIRECT_EXEMPT = [r"^api/health/?$"]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = env("DJANGO_SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = env("DJANGO_CSRF_COOKIE_SAMESITE", default="Lax")
SECURE_HSTS_SECONDS = env("DJANGO_SECURE_HSTS_SECONDS")
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
if env.bool("EDI_ALLOW_LOVABLE_ORIGINS", default=False):
    _lovable_regexes = [
        r"^https://[\w.-]+\.lovable\.app$",
        r"^https://[\w.-]+\.lovableproject\.com$",
    ]
    CORS_ALLOWED_ORIGIN_REGEXES = list(CORS_ALLOWED_ORIGIN_REGEXES) + [
        r for r in _lovable_regexes if r not in CORS_ALLOWED_ORIGIN_REGEXES
    ]

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Production always requires authentication (JWT Bearer or session).
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

DATABASES = {
    "default": {
        "ENGINE": env("DJANGO_DB_ENGINE", default="django.db.backends.postgresql"),
        "NAME": env("POSTGRES_DB", default="edi"),
        "USER": env("POSTGRES_USER", default="edi"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": env("DJANGO_DB_CONN_MAX_AGE"),
        "OPTIONS": {"sslmode": env("POSTGRES_SSLMODE", default="prefer")},
    }
}
