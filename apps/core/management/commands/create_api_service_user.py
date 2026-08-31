"""Create / rotate the RedArt EDI API service user (non-admin)."""

from __future__ import annotations

import os
import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.auth_constants import API_SERVICE_GROUP_NAME

User = get_user_model()

MIN_GENERATED_PASSWORD_LENGTH = 32


def _generate_password(length: int = MIN_GENERATED_PASSWORD_LENGTH) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    parts = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*-_=+"),
    ]
    parts += [secrets.choice(alphabet) for _ in range(max(0, length - len(parts)))]
    secrets.SystemRandom().shuffle(parts)
    return "".join(parts)


class Command(BaseCommand):
    help = (
        "Create or update a non-privileged API service user for RedArt "
        f"(group: {API_SERVICE_GROUP_NAME}). Prefer --password-from-env or "
        "--generate-password. Never commit passwords."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None)
        parser.add_argument("--email", default=None)
        parser.add_argument("--password", default=None)
        parser.add_argument("--password-from-env", action="store_true")
        parser.add_argument("--generate-password", action="store_true")
        parser.add_argument(
            "--rotate-password",
            action="store_true",
            help="Required to change password when the user already exists "
            "(unless --generate-password / --password-from-env).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = (
            options["username"]
            or getattr(settings, "EDI_API_SERVICE_USERNAME", None)
            or os.environ.get("EDI_API_SERVICE_USERNAME", "")
        ).strip()
        email = (
            options["email"]
            or getattr(settings, "EDI_API_SERVICE_EMAIL", None)
            or os.environ.get("EDI_API_SERVICE_EMAIL", "")
        ).strip()

        if not username:
            raise CommandError(
                "Username required (--username or EDI_API_SERVICE_USERNAME)."
            )
        if len(username) < 3:
            raise CommandError("Username must be at least 3 characters.")
        if any(ch.isspace() for ch in username):
            raise CommandError("Username must not contain whitespace.")
        if not email:
            email = f"{username}@edi.local"

        password_sources = sum(
            [
                bool(options["password"]),
                bool(options["password_from_env"]),
                bool(options["generate_password"]),
            ]
        )
        if password_sources != 1:
            raise CommandError(
                "Choose exactly one of: --password-from-env, "
                "--generate-password, or --password."
            )

        if options["password_from_env"]:
            password = os.environ.get("EDI_API_SERVICE_PASSWORD") or ""
            if not password:
                raise CommandError("EDI_API_SERVICE_PASSWORD is empty.")
        elif options["generate_password"]:
            password = _generate_password()
        else:
            password = options["password"]

        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        group, _ = Group.objects.get_or_create(name=API_SERVICE_GROUP_NAME)
        user = User.objects.filter(username=username).first()
        created = user is None

        if user is not None and not (
            options["rotate_password"]
            or options["generate_password"]
            or options["password_from_env"]
        ):
            # Explicit --password on existing user still needs --rotate-password.
            raise CommandError(
                f"User '{username}' already exists. "
                "Re-run with --rotate-password to change the password."
            )

        if user is None:
            user = User(username=username)

        user.email = email
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()
        user.groups.add(group)

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} API service user "
                f"username={username} group={API_SERVICE_GROUP_NAME} "
                f"staff=False superuser=False"
            )
        )
        if options["generate_password"]:
            self.stdout.write(
                self.style.WARNING(
                    "Generated password (store securely; shown once):\n"
                    f"{password}"
                )
            )
        self.stdout.write(
            'Obtain token: POST /api/v1/auth/token/ '
            '{"username": "...", "password": "..."}'
        )
