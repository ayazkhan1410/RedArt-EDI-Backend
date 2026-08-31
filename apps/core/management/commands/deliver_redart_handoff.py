"""Print a secure RedArt / Lovable handoff pack (API URL + service credentials).

Never commit the printed password. Deliver via 1Password / Signal / sealed channel.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.core.auth_constants import API_SERVICE_GROUP_NAME
from apps.core.management.commands.create_api_service_user import _generate_password

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Print TEST API handoff for RedArt/Lovable: public URL, token endpoint, "
        "and optional service-user create. Secrets printed once — not written to disk."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=None,
            help="Service username (default EDI_API_SERVICE_USERNAME or redart_api).",
        )
        parser.add_argument(
            "--create-user",
            action="store_true",
            help="Create/rotate service user with a generated password.",
        )
        parser.add_argument(
            "--as-json",
            action="store_true",
            help="Emit machine-readable JSON (still contains secrets — handle carefully).",
        )

    def handle(self, *args, **options):
        base = (getattr(settings, "EDI_PUBLIC_BASE_URL", None) or "").rstrip("/")
        if not base:
            base = "http://127.0.0.1:7000"
            self.stdout.write(
                self.style.WARNING(
                    "EDI_PUBLIC_BASE_URL unset — using local Docker default. "
                    "Set EDI_PUBLIC_BASE_URL after Render/Railway/VPS deploy."
                )
            )

        username = (
            options["username"]
            or getattr(settings, "EDI_API_SERVICE_USERNAME", None)
            or "redart_api"
        ).strip()

        password = None
        if options["create_user"]:
            password = _generate_password()
            call_command(
                "create_api_service_user",
                username=username,
                password=password,
                rotate_password=True,
            )
        else:
            user = User.objects.filter(username=username).first()
            if user is None:
                raise CommandError(
                    f"User '{username}' not found. Re-run with --create-user."
                )
            if not user.groups.filter(name=API_SERVICE_GROUP_NAME).exists():
                raise CommandError(
                    f"User '{username}' is not in group {API_SERVICE_GROUP_NAME}."
                )

        pack = {
            "architecture": (
                "Call EDI with JWT from RedArt/Lovable. "
                "Start at GET /api/v1/integration/lovable/ and docs/LOVABLE_QUICKSTART.md."
            ),
            "edi_public_base_url": base,
            "health_url": f"{base}/api/health/",
            "swagger_url": f"{base}/api/docs/",
            "token_url": f"{base}/api/v1/auth/token/",
            "api_prefix": f"{base}/api/v1/",
            "service_username": username,
            "service_password": password
            or "<ask-ops-for-password-or-use--create-user>",
            "auth_header": "Authorization: Bearer <access_from_token_url>",
            "lovable_notes": {
                "quickstart": "docs/LOVABLE_QUICKSTART.md",
                "catalog_url": f"{base}/api/v1/integration/lovable/",
                "swagger_url": f"{base}/api/docs/",
                "env": "VITE_EDI_API_BASE_URL + service username/password",
            },
            "samples_doc": "docs/REDART_API_SAMPLES.md",
            "deploy_doc": "docs/LOVABLE_EDI_DEPLOY.md",
            "quickstart_doc": "docs/LOVABLE_QUICKSTART.md",
        }

        if options["as_json"]:
            self.stdout.write(json.dumps(pack, indent=2))
            return

        self.stdout.write(
            self.style.SUCCESS("=== RedArt / Lovable EDI handoff (SECRET) ===")
        )
        self.stdout.write(f"API base URL:     {pack['edi_public_base_url']}")
        self.stdout.write(f"Health:           {pack['health_url']}")
        self.stdout.write(f"Swagger:          {pack['swagger_url']}")
        self.stdout.write(f"Token:            {pack['token_url']}")
        self.stdout.write(f"Service username: {pack['service_username']}")
        self.stdout.write(
            self.style.WARNING(f"Service password: {pack['service_password']}")
        )
        self.stdout.write("")
        self.stdout.write(pack["architecture"])
        self.stdout.write(f"Lovable catalog:  {pack['lovable_notes']['catalog_url']}")
        self.stdout.write(
            "Deliver this block via 1Password / Signal — do not commit or paste into git."
        )
