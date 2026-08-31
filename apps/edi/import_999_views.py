"""Import 999 — list/detail + manual SFTP poll API."""

from __future__ import annotations

import logging
import traceback

from django.db.models import Q
from django.http import Http404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.core.soft_delete import (
    client_error_message,
    get_active_object_or_404,
    get_api_object_or_404,
    hard_delete_permission_error,
    parse_hard_flag,
)

from apps.claim.utils.validators import parse_optional_int
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response
from apps.edi.models import EDI999Import
from apps.edi.serializers import (
    EDI999ImportListSerializer,
    EDI999ImportSerializer,
    PollEDI999ImportsSerializer,
)
from apps.edi.tasks import poll_edi_999_imports
from apps.edi.utils.import_999 import queue_edi_999_import_poll

logger = logging.getLogger(__name__)

TAG = "edi_999_import"


class EDI999ImportListAPIView(APIView):
    @extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("status", str, required=False),
            OpenApiParameter("credentials_id", int, required=False),
            OpenApiParameter("batch_id", int, required=False),
            OpenApiParameter("search", str, required=False),
        ],
        responses={200: EDI999ImportListSerializer(many=True)},
    )
    def get(self, request):
        try:
            rows = EDI999Import.objects.with_relations().order_by("-id")
            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                rows = rows.filter(is_active=True)

            status_filter = (request.query_params.get("status") or "").strip().upper()
            if status_filter:
                rows = rows.filter(status=status_filter)

            credentials_id = parse_optional_int(
                request.query_params.get("credentials_id"), "credentials_id"
            )
            if credentials_id is not None:
                rows = rows.filter(credentials_id=credentials_id)

            batch_id = parse_optional_int(
                request.query_params.get("batch_id"), "batch_id"
            )
            if batch_id is not None:
                rows = rows.filter(batch_id=batch_id)

            search = (request.query_params.get("search") or "").strip()
            if search:
                rows = rows.filter(
                    Q(filename__icontains=search)
                    | Q(remote_path__icontains=search)
                    | Q(file_hash__icontains=search)
                    | Q(message__icontains=search)
                    | Q(celery_task_id__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request)
            data = EDI999ImportListSerializer(page, many=True).data
            return paginator.get_paginated_response(data)
        except Exception:
            logger.error("List EDI999Import failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list Import 999 rows.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EDI999ImportDetailAPIView(APIView):
    @extend_schema(tags=[TAG], responses={200: EDI999ImportSerializer})
    def get(self, request, pk):
        try:
            row = get_active_object_or_404(
                EDI999Import.objects.with_relations(),
                pk=pk,
            )
            return success_response(
                "Import 999 detail.",
                data=EDI999ImportSerializer(row).data,
            )
        except Http404:
            raise
        except Exception:
            logger.error("Detail EDI999Import id=%s failed:\n%s", pk, traceback.format_exc())
            return error_response(
                "Unable to load Import 999 row.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EDI999ImportPollAPIView(APIView):
    """
    Manual trigger: discover inbound 999 files on SFTP and start importing.
    Prefer async_mode=true so the HTTP call returns immediately with Celery task id.
    """

    @extend_schema(
        tags=[TAG],
        request=PollEDI999ImportsSerializer,
        examples=[
            OpenApiExample(
                "Start Import 999 poll",
                value={"credentials_id": None, "batch_id": None, "async_mode": True},
                request_only=True,
            )
        ],
        responses={202: PollEDI999ImportsSerializer},
    )
    def post(self, request):
        try:
            serializer = PollEDI999ImportsSerializer(data=request.data or {})
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            credentials_id = serializer.validated_data.get("credentials_id")
            batch_id = serializer.validated_data.get("batch_id")
            async_mode = serializer.validated_data.get("async_mode", True)

            if async_mode:
                async_result = poll_edi_999_imports.delay(credentials_id, batch_id)
                return success_response(
                    "Importing started.",
                    data={
                        "message": "Importing started.",
                        "celery_task_id": async_result.id,
                        "async_mode": True,
                    },
                    status_code=status.HTTP_202_ACCEPTED,
                )

            result = queue_edi_999_import_poll(
                credentials_id=credentials_id,
                batch_id=batch_id,
            )
            return success_response(
                "Importing started.",
                data={**result, "async_mode": False},
                status_code=status.HTTP_202_ACCEPTED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Poll Import 999 failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to start Import 999 poll.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
