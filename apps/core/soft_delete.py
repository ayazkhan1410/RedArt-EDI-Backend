"""Shared API helpers for soft-delete and hard-delete policy."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status

from apps.core.utils.responses import error_response


def get_active_object_or_404(queryset, **kwargs):
    """Like get_object_or_404 but requires is_active=True when the model has it."""
    model = getattr(queryset, "model", None)
    if model is not None and hasattr(model, "is_active"):
        kwargs.setdefault("is_active", True)
    return get_object_or_404(queryset, **kwargs)


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


# Back-compat alias used during rollout (raises — prefer hard_delete_permission_error).
def require_staff_for_hard_delete(request, *, hard: bool):
    denied = hard_delete_permission_error(request, hard)
    if denied is not None:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("Hard delete requires a staff account.")
