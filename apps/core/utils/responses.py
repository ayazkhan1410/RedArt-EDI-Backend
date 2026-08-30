"""Shared API response helpers."""

from rest_framework import status
from rest_framework.response import Response


def error_response(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    body = {"success": False, "message": message}
    if errors is not None:
        body["errors"] = errors
    return Response(body, status=status_code)


def success_response(message, data=None, status_code=status.HTTP_200_OK):
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return Response(body, status=status_code)
