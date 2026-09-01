"""Shared API helpers for soft-delete and hard-delete policy."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status

from apps.core.utils.responses import error_response


def get_active_object_or_404(queryset, **kwargs):
    """Like get_object_or_404 but requires is_active=True when the model has it."""
    model = getattr(queryset, "model", None)
    if model is None and hasattr(queryset, "_meta"):
        model = queryset
    if model is not None and hasattr(model, "is_active"):
        kwargs.setdefault("is_active", True)
    return get_object_or_404(queryset, **kwargs)


def get_api_object_or_404(queryset, *, hard: bool = False, **kwargs):
    """
    Resolve an object for API detail/update/delete.
    Soft paths hide inactive rows (404). Hard delete may target any row.
    """
    if hard:
        return get_object_or_404(queryset, **kwargs)
    return get_active_object_or_404(queryset, **kwargs)


def parse_hard_flag(request) -> bool:
    return (request.query_params.get("hard") or "").lower() in (
        "1",
        "true",
        "yes",
    )


def hard_delete_permission_error(request, hard: bool):
    """
    Return a 403 Response when hard-delete is requested by a non-staff user.
    Callers: `denied = hard_delete_permission_error(...); if denied: return denied`
    """
    if not hard:
        return None
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not (
        user.is_staff or user.is_superuser
    ):
        return error_response(
            "Hard delete requires a staff account.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return None


def staff_include_inactive(request) -> bool:
    """include_inactive list param — staff only."""
    flag = (request.query_params.get("include_inactive") or "").lower()
    if flag not in ("1", "true", "yes"):
        return False
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )


def filter_active_for_list(request, queryset):
    """Apply is_active=True unless staff explicitly requests inactive rows."""
    if staff_include_inactive(request):
        return queryset
    if hasattr(queryset.model, "is_active"):
        return queryset.filter(is_active=True)
    return queryset


def client_error_message(exc, *, fallback: str = "Request failed.", max_length: int = 500) -> str:
    """
    Safe client-facing message from an exception.
    Keeps short ValueError/Validation text; strips traceback-like payloads.
    """
    text = str(getattr(exc, "detail", None) or exc or "").strip()
    if not text:
        return fallback
    lowered = text.lower()
    if "traceback (most recent call last)" in lowered or "\n  file \"" in lowered:
        return fallback
    # Prefer first line only (avoid accidental multi-line dumps).
    text = text.splitlines()[0].strip()
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text or fallback


# Back-compat alias used during rollout (raises — prefer hard_delete_permission_error).
def require_staff_for_hard_delete(request, *, hard: bool):
    denied = hard_delete_permission_error(request, hard)
    if denied is not None:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("Hard delete requires a staff account.")
