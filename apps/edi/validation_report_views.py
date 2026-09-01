"""Edifecs validation report import and listing."""

import logging
import traceback

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.core.soft_delete import client_error_message, get_active_object_or_404
from apps.core.utils.responses import error_response, success_response
from apps.edi.models import EDIValidationReport
from apps.edi.serializers import (
    EDIValidationReportIdSerializer,
    EDIValidationReportListSerializer,
    EDIValidationReportSerializer,
    ImportValidationReportSerializer,
)
from apps.edi.utils.service import import_validation_report

logger = logging.getLogger(__name__)

TAG = "edi_validation_report"


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("batch_id", int, required=False),
            OpenApiParameter("report_type", str, required=False),
            OpenApiParameter("status", str, required=False),
        ],
        responses={200: EDIValidationReportListSerializer(many=True)},
    ),
)
class EDIValidationReportListAPIView(APIView):
    def get(self, request):
        try:
            rows = EDIValidationReport.objects.with_relations().order_by("-id")
            rows = rows.filter(is_active=True)

            batch_id = request.query_params.get("batch_id")
            if batch_id and str(batch_id).isdigit():
                rows = rows.filter(batch_id=int(batch_id))

            report_type = request.query_params.get("report_type", "").strip().upper()
            if report_type:
                rows = rows.filter(report_type=report_type)

            status_filter = request.query_params.get("status", "").strip().upper()
            if status_filter:
                rows = rows.filter(status=status_filter)

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            data = EDIValidationReportListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "Validation reports retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error("List validation reports failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list validation reports.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EDIValidationReportDetailAPIView(APIView):
    @extend_schema(tags=[TAG], responses={200: EDIValidationReportSerializer})
    def get(self, request, pk):
        try:
            row = get_active_object_or_404(
                EDIValidationReport.objects.with_relations(), pk=pk
            )
            return success_response(
                "Validation report retrieved successfully.",
                data=EDIValidationReportSerializer(row).data,
            )
        except Exception:
            logger.error("Get validation report id=%s failed:\n%s", pk, traceback.format_exc())
            return error_response(
                "Unable to retrieve validation report.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EDIValidationReportImportAPIView(APIView):
    @extend_schema(
        tags=[TAG],
        request=ImportValidationReportSerializer,
        responses={201: EDIValidationReportIdSerializer},
    )
    def post(self, request):
        try:
            serializer = ImportValidationReportSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            data = serializer.validated_data
            row, parsed, created = import_validation_report(
                content=data["content"],
                batch_id=data.get("batch_id"),
                edi_file_id=data.get("edi_file_id"),
                raw_file_ref=data.get("raw_file_ref"),
                file_name=data.get("file_name"),
            )
            return success_response(
                "Validation report imported successfully." if created else "Validation report already imported.",
                data={
                    "id": row.id,
                    "created": created,
                    "report_type": row.report_type,
                    "status": row.status,
                    "task_id": row.task_id,
                    "error_count": row.error_count,
                    "parsed": parsed,
                },
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Import validation report failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to import validation report.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
