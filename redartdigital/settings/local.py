"""Local development settings."""

from redartdigital.settings.base import *  # noqa: F401, F403
from redartdigital.settings.base import REST_FRAMEWORK, env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-local-only-change-before-any-shared-use",
)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Local Docker SFTP often has no host-key fingerprint configured.
EDI_SFTP_REQUIRE_HOST_FINGERPRINT = env.bool(
    "EDI_SFTP_REQUIRE_HOST_FINGERPRINT", default=False
)

# Prefer authenticated local APIs. Set API_REQUIRE_AUTH=false only for open Swagger demos.
if env.bool("API_REQUIRE_AUTH", default=True):
    REST_FRAMEWORK = {
        **REST_FRAMEWORK,
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.IsAuthenticated",
        ],
    }
else:
    REST_FRAMEWORK = {
        **REST_FRAMEWORK,
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.AllowAny",
        ],
    }
