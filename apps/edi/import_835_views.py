"""Import 835 — list/detail + manual SFTP poll API."""

from __future__ import annotations

import logging
import traceback

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.claim.utils.validators import parse_optional_int
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response
from apps.edi.models import EDI835Import
from apps.edi.serializers import (
    EDI835ImportListSerializer,
    EDI835ImportSerializer,
    PollEDI835ImportsSerializer,
)
from apps.edi.tasks import poll_edi_835_imports
from apps.edi.utils.import_835_poll import queue_edi_835_import_poll

logger = logging.getLogger(__name__)

TAG = "edi_835_import"


class EDI835ImportListAPIView(APIView):
    @extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("status", str, required=False),
            OpenApiParameter("credentials_id", int, required=False),
            OpenApiParameter("search", str, required=False),
        ],
        responses={200: EDI835ImportListSerializer(many=True)},
    )
    def get(self, request):
        try:
            rows = EDI835Import.objects.with_relations().order_by("-id")
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
            data = EDI835ImportListSerializer(page, many=True).data
            return paginator.get_paginated_response(data)
        except Exception:
            logger.error("List EDI835Import failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list Import 835 rows.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EDI835ImportDetailAPIView(APIView):
    @extend_schema(tags=[TAG], responses={200: EDI835ImportSerializer})
    def get(self, request, pk):
        try:
            row = get_object_or_404(EDI835Import.objects.with_relations(), pk=pk)
            return success_response(
                "Import 835 detail.",
                data=EDI835ImportSerializer(row).data,
            )
        except Http404:
            raise
        except Exception:
            logger.error(
                "Detail EDI835Import id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to load Import 835 row.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EDI835ImportPollAPIView(APIView):
    @extend_schema(
        tags=[TAG],
        summary="Poll SFTP for inbound 835 ERA files",
        request=PollEDI835ImportsSerializer,
        examples=[
            OpenApiExample(
                "Start Import 835 poll",
                value={"credentials_id": None, "async_mode": True},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        try:
            serializer = PollEDI835ImportsSerializer(data=request.data or {})
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            credentials_id = serializer.validated_data.get("credentials_id")
            async_mode = serializer.validated_data.get("async_mode", True)

            if async_mode:
                async_result = poll_edi_835_imports.delay(credentials_id)
                return success_response(
                    "Importing started.",
                    data={
                        "message": "Importing started.",
                        "celery_task_id": async_result.id,
                        "async_mode": True,
                    },
                    status_code=status.HTTP_202_ACCEPTED,
                )

            result = queue_edi_835_import_poll(credentials_id=credentials_id)
            return success_response(
                "Importing started.",
                data={**result, "async_mode": False},
                status_code=status.HTTP_202_ACCEPTED,
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Poll EDI835Import failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to start Import 835 poll.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
