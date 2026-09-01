"""DRF permission classes for EDI API role separation."""

from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.core.auth_constants import API_SERVICE_GROUP_NAME


class IsStaffUser(BasePermission):
    """Staff or superuser only."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
        )


class IsServiceOrStaffUser(BasePermission):
    """RedArt service JWT, staff, or superuser."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        return user.groups.filter(name=API_SERVICE_GROUP_NAME).exists()


class CanOrchestrateEDI(BasePermission):
    """
    SFTP poll, pilot orchestration, upload queue — service account or staff.
  """

    def has_permission(self, request, view):
        return IsServiceOrStaffUser().has_permission(request, view)


class CanImportEDI(BasePermission):
    """
    Manual X12 import / apply claim status — service account or staff.
    Pair with apply_claim_status default false on paste imports.
    """

    def has_permission(self, request, view):
        return IsServiceOrStaffUser().has_permission(request, view)


class DefaultAuthenticated(BasePermission):
    """Alias matching project default gate."""

    def has_permission(self, request, view):
        return IsAuthenticated().has_permission(request, view)
