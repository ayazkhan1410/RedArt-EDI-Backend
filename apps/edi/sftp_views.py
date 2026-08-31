import logging
import traceback

from django.db import IntegrityError
from django.db.models import Q, ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.soft_delete import hard_delete_permission_error, parse_hard_flag

from apps.claim.utils.validators import parse_optional_int
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response
from apps.edi.models import SFTPCredentials, SFTPDirectory
from apps.edi.sftp_serializers import (
    SFTPCredentialsIdSerializer,
    SFTPCredentialsListSerializer,
    SFTPCredentialsSerializer,
    SFTPDirectoryIdSerializer,
    SFTPDirectoryListSerializer,
    SFTPDirectorySerializer,
)

logger = logging.getLogger(__name__)

CRED_TAG = "sftp_credentials"
DIR_TAG = "sftp_directory"

CRED_EXAMPLE = OpenApiExample(
    "Sample SFTP credentials",
    value={
        "name": "CO Medicaid TEST MFT",
        "trading_partner": 1,
        "environment": "TEST",
        "host": "mft-test.example.com",
        "port": 22,
        "username": "redart_test",
        "auth_type": "PASSWORD",
        "password": "change-me",
        "timeout_seconds": 30,
        "is_active": True,
    },
    request_only=True,
)

DIR_EXAMPLE = OpenApiExample(
    "Sample SFTP directory",
    value={
        "credentials": 1,
        "name": "837P outbound / 999 inbound",
        "purpose": "OUTBOUND_837P",
        "sending_path": "/outbound/837p",
        "receiving_path": "/inbound/999",
        "is_active": True,
    },
    request_only=True,
)


@extend_schema_view(
    get=extend_schema(
        tags=[CRED_TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("environment", str, required=False),
            OpenApiParameter("trading_partner_id", int, required=False),
            OpenApiParameter("search", str, required=False),
        ],
        responses={200: SFTPCredentialsListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[CRED_TAG],
        request=SFTPCredentialsSerializer,
        examples=[CRED_EXAMPLE],
        responses={201: SFTPCredentialsIdSerializer},
    ),
)
class SFTPCredentialsListCreateAPIView(APIView):
    def get(self, request):
        try:
            rows = SFTPCredentials.objects.with_relations().order_by("-id")
            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                rows = rows.filter(is_active=True)

            environment = request.query_params.get("environment", "").strip()
            if environment:
                rows = rows.filter(environment=environment.upper())

            tp_id = parse_optional_int(
                request.query_params.get("trading_partner_id"),
                "trading_partner_id",
            )
            if tp_id:
                rows = rows.filter(trading_partner_id=tp_id)

            search = request.query_params.get("search", "").strip()
            if search:
                rows = rows.filter(
                    Q(name__icontains=search)
                    | Q(host__icontains=search)
                    | Q(username__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            data = SFTPCredentialsListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "SFTP credentials retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error("List SFTP credentials failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list SFTP credentials.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = SFTPCredentialsSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            logger.info("Created SFTP credentials id=%s", row.id)
            return success_response(
                "SFTP credentials created successfully.",
                data={"id": row.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return error_response(
                "Unable to create SFTP credentials due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create SFTP credentials failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create SFTP credentials.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[CRED_TAG], responses={200: SFTPCredentialsSerializer}),
    put=extend_schema(
        tags=[CRED_TAG],
        request=SFTPCredentialsSerializer,
        examples=[CRED_EXAMPLE],
        responses={200: SFTPCredentialsIdSerializer},
    ),
    patch=extend_schema(
        tags=[CRED_TAG],
        request=SFTPCredentialsSerializer,
        examples=[CRED_EXAMPLE],
        responses={200: SFTPCredentialsIdSerializer},
    ),
    delete=extend_schema(
        tags=[CRED_TAG],
        parameters=[
            OpenApiParameter(
                "hard",
                str,
                required=False,
                description="Pass true to permanently delete instead of soft-deactivate.",
            ),
        ],
        responses={200: SFTPCredentialsIdSerializer},
    ),
)
class SFTPCredentialsDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            row = get_object_or_404(
                SFTPCredentials.objects.with_relations(), pk=pk
            )
            return success_response(
                "SFTP credentials retrieved successfully.",
                data=SFTPCredentialsSerializer(row).data,
            )
        except Http404:
            return error_response(
                "SFTP credentials not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get SFTP credentials id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to retrieve SFTP credentials.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            row = get_object_or_404(
                SFTPCredentials.objects.with_relations(), pk=pk
            )
            serializer = SFTPCredentialsSerializer(
                row, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            return success_response(
                "SFTP credentials updated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "SFTP credentials not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            return error_response(
                "Unable to update SFTP credentials due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update SFTP credentials id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update SFTP credentials.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            row = get_object_or_404(
                SFTPCredentials.objects.with_relations(), pk=pk
            )
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            if hard_delete:
                if row.directories.filter(is_active=True).exists():
                    return error_response(
                        "Cannot hard-delete credentials that still have active directories.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                row_id = row.id
                try:
                    row.delete()
                except ProtectedError:
                    return error_response(
                        "Cannot hard-delete credentials referenced by directories.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                return success_response(
                    "SFTP credentials permanently deleted.",
                    data={"id": row_id},
                )
            if not row.is_active:
                return success_response(
                    "SFTP credentials are already inactive.",
                    data={"id": row.id},
                )
            row.is_active = False
            row.save(update_fields=["is_active", "updated_at"])
            return success_response(
                "SFTP credentials deactivated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "SFTP credentials not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete SFTP credentials id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete SFTP credentials.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(
        tags=[DIR_TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("credentials_id", int, required=False),
            OpenApiParameter("purpose", str, required=False),
            OpenApiParameter("search", str, required=False),
        ],
        responses={200: SFTPDirectoryListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[DIR_TAG],
        request=SFTPDirectorySerializer,
        examples=[DIR_EXAMPLE],
        responses={201: SFTPDirectoryIdSerializer},
    ),
)
class SFTPDirectoryListCreateAPIView(APIView):
    def get(self, request):
        try:
            rows = SFTPDirectory.objects.with_relations().order_by("-id")
            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                rows = rows.filter(is_active=True)

            cred_id = parse_optional_int(
                request.query_params.get("credentials_id"), "credentials_id"
            )
            if cred_id:
                rows = rows.filter(credentials_id=cred_id)

            purpose = request.query_params.get("purpose", "").strip()
            if purpose:
                rows = rows.filter(purpose=purpose.upper())

            search = request.query_params.get("search", "").strip()
            if search:
                rows = rows.filter(
                    Q(name__icontains=search)
                    | Q(sending_path__icontains=search)
                    | Q(receiving_path__icontains=search)
                    | Q(credentials__name__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            data = SFTPDirectoryListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "SFTP directories retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error("List SFTP directories failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list SFTP directories.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = SFTPDirectorySerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            logger.info("Created SFTP directory id=%s", row.id)
            return success_response(
                "SFTP directory created successfully.",
                data={"id": row.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return error_response(
                "Unable to create SFTP directory due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create SFTP directory failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create SFTP directory.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[DIR_TAG], responses={200: SFTPDirectorySerializer}),
    put=extend_schema(
        tags=[DIR_TAG],
        request=SFTPDirectorySerializer,
        examples=[DIR_EXAMPLE],
        responses={200: SFTPDirectoryIdSerializer},
    ),
    patch=extend_schema(
        tags=[DIR_TAG],
        request=SFTPDirectorySerializer,
        examples=[DIR_EXAMPLE],
        responses={200: SFTPDirectoryIdSerializer},
    ),
    delete=extend_schema(
        tags=[DIR_TAG],
        parameters=[
            OpenApiParameter(
                "hard",
                str,
                required=False,
                description="Pass true to permanently delete instead of soft-deactivate.",
            ),
        ],
        responses={200: SFTPDirectoryIdSerializer},
    ),
)
class SFTPDirectoryDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            row = get_object_or_404(SFTPDirectory.objects.with_relations(), pk=pk)
            return success_response(
                "SFTP directory retrieved successfully.",
                data=SFTPDirectorySerializer(row).data,
            )
        except Http404:
            return error_response(
                "SFTP directory not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get SFTP directory id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to retrieve SFTP directory.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            row = get_object_or_404(SFTPDirectory.objects.with_relations(), pk=pk)
            serializer = SFTPDirectorySerializer(
                row, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            return success_response(
                "SFTP directory updated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "SFTP directory not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            return error_response(
                "Unable to update SFTP directory due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update SFTP directory id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update SFTP directory.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            row = get_object_or_404(SFTPDirectory.objects.with_relations(), pk=pk)
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            if hard_delete:
                row_id = row.id
                row.delete()
                return success_response(
                    "SFTP directory permanently deleted.",
                    data={"id": row_id},
                )
            if not row.is_active:
                return success_response(
                    "SFTP directory is already inactive.",
                    data={"id": row.id},
                )
            row.is_active = False
            row.save(update_fields=["is_active", "updated_at"])
            return success_response(
                "SFTP directory deactivated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "SFTP directory not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete SFTP directory id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete SFTP directory.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
