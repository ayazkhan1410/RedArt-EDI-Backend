"""Shared API response helpers."""

from rest_framework import status
from rest_framework.response import Response


def error_response(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Standard error envelope.

    If `message` contains bullet-point lines (• …), they are automatically
    split into `errors[]` so the FE always gets a structured list — never
    just one long string.  Callers can also pass an explicit `errors` list.
    """
    body = {"success": False, "message": message}

    # Auto-extract bullet lines from multi-line readiness / validation messages.
    if errors is None and message and "\n" in str(message):
        bullets = [
            line.lstrip("• ").strip()
            for line in str(message).splitlines()
            if line.strip().startswith("•")
        ]
        if bullets:
            errors = bullets

    if errors is not None:
        body["errors"] = errors

    return Response(body, status=status_code)


def success_response(message, data=None, status_code=status.HTTP_200_OK):
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return Response(body, status=status_code)
