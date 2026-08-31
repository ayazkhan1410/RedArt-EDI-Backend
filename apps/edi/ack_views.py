import logging
import traceback

from django.db import IntegrityError
from django.db.models import Q
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

from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response
from apps.edi.models import EDIAcknowledgement
from apps.edi.serializers import (
    ApplyEDIAcknowledgementSerializer,
    EDIAcknowledgementIdSerializer,
    EDIAcknowledgementListSerializer,
    EDIAcknowledgementSerializer,
)
from apps.edi.utils.service import apply_edi_acknowledgement
from apps.edi.utils.validators import clean_optional_text

logger = logging.getLogger(__name__)

TAG = "edi_acknowledgement"

WRITE_EXAMPLE = OpenApiExample(
    "Sample 999 acknowledgement",
    value={
        "batch": 1,
        "ack_type": "999",
        "status": "ACCEPTED",
        "affected_st02": "0001",
        "raw_file_ref": "s3://edi/999_001.edi",
        "is_active": True,
    },
    request_only=True,
)

APPLY_EXAMPLE = OpenApiExample(
    "Apply 999 and update claims",
    value={
        "batch_id": 1,
        "ack_type": "999",
        "status": "ACCEPTED",
        "affected_st02": "0001",
        "raw_file_ref": "s3://edi/999_001.edi",
        "apply_claim_status": True,
    },
    request_only=True,
)


def _parse_optional_int(raw, field_name):
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValidationError({field_name: ["Must be an integer."]})


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("search", str, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("batch_id", int, required=False),
            OpenApiParameter("status", str, required=False),
            OpenApiParameter("ack_type", str, required=False),
            OpenApiParameter("affected_st02", str, required=False),
        ],
        responses={200: EDIAcknowledgementListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=EDIAcknowledgementSerializer,
        examples=[WRITE_EXAMPLE],
        responses={201: EDIAcknowledgementIdSerializer},
    ),
)
class EDIAcknowledgementListCreateAPIView(APIView):
    def get(self, request):
        try:
            rows = EDIAcknowledgement.objects.with_relations().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                rows = rows.filter(is_active=True)

            batch_id = _parse_optional_int(
                request.query_params.get("batch_id"), "batch_id"
            )
            if batch_id:
                rows = rows.filter(batch_id=batch_id)

            status_filter = request.query_params.get("status", "").strip()
            if status_filter:
                rows = rows.filter(status=status_filter.upper())

            ack_type = request.query_params.get("ack_type", "").strip()
            if ack_type:
                rows = rows.filter(ack_type=ack_type.upper())

            st02 = clean_optional_text(request.query_params.get("affected_st02"))
            if st02:
                if st02.isdigit() and len(st02) <= 4:
                    st02 = st02.zfill(4)
                rows = rows.filter(affected_st02=st02)

            search = request.query_params.get("search", "").strip()
            if search:
                rows = rows.filter(
                    Q(raw_file_ref__icontains=search)
                    | Q(message__icontains=search)
                    | Q(affected_st02__icontains=search)
                    | Q(batch__batch_number__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            data = EDIAcknowledgementListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "EDI acknowledgements retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error(
                "List EDI acknowledgements failed:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to list EDI acknowledgements.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """Store acknowledgement only (no automatic claim status apply)."""
        try:
            serializer = EDIAcknowledgementSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            logger.info("Created EDI acknowledgement id=%s", row.id)
            return success_response(
                "EDI acknowledgement created successfully.",
                data={"id": row.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return error_response(
                "Unable to create EDI acknowledgement due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Create EDI acknowledgement failed:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to create EDI acknowledgement.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[TAG], responses={200: EDIAcknowledgementSerializer}),
    put=extend_schema(
        tags=[TAG],
        request=EDIAcknowledgementSerializer,
        examples=[WRITE_EXAMPLE],
        responses={200: EDIAcknowledgementIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=EDIAcknowledgementSerializer,
        examples=[WRITE_EXAMPLE],
        responses={200: EDIAcknowledgementIdSerializer},
    ),
    delete=extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter(
                "hard",
                str,
                required=False,
                description="Pass true to permanently delete instead of soft-deactivate.",
            ),
        ],
        responses={200: EDIAcknowledgementIdSerializer},
    ),
)
class EDIAcknowledgementDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            row = get_object_or_404(
                EDIAcknowledgement.objects.with_relations(), pk=pk
            )
            return success_response(
                "EDI acknowledgement retrieved successfully.",
                data=EDIAcknowledgementSerializer(row).data,
            )
        except Http404:
            return error_response(
                "EDI acknowledgement not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get EDI acknowledgement id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to retrieve EDI acknowledgement.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            row = get_object_or_404(
                EDIAcknowledgement.objects.with_relations(), pk=pk
            )
            serializer = EDIAcknowledgementSerializer(
                row, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            logger.info("Updated EDI acknowledgement id=%s", row.id)
            return success_response(
                "EDI acknowledgement updated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "EDI acknowledgement not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            return error_response(
                "Unable to update EDI acknowledgement due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update EDI acknowledgement id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update EDI acknowledgement.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            row = get_object_or_404(
                EDIAcknowledgement.objects.with_relations(), pk=pk
            )
            hard_delete = request.query_params.get("hard", "").lower() in (
                "1",
                "true",
                "yes",
            )
            if hard_delete:
                row_id = row.id
                row.delete()
                logger.info("Hard deleted EDI acknowledgement id=%s", row_id)
                return success_response(
                    "EDI acknowledgement permanently deleted.",
                    data={"id": row_id},
                )
            if not row.is_active:
                return success_response(
                    "EDI acknowledgement is already inactive.",
                    data={"id": row.id},
                )
            row.is_active = False
            row.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated EDI acknowledgement id=%s", row.id)
            return success_response(
                "EDI acknowledgement deactivated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "EDI acknowledgement not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete EDI acknowledgement id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete EDI acknowledgement.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EDIAcknowledgementApplyAPIView(APIView):
    """Create acknowledgement and apply claim / EDIFile / batch side effects."""

    @extend_schema(
        tags=[TAG],
        request=ApplyEDIAcknowledgementSerializer,
        examples=[APPLY_EXAMPLE],
        responses={201: EDIAcknowledgementIdSerializer},
    )
    def post(self, request):
        try:
            serializer = ApplyEDIAcknowledgementSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            data = serializer.validated_data
            ack, claim_ids = apply_edi_acknowledgement(
                batch_id=data["batch_id"],
                ack_type=data.get("ack_type"),
                status=data.get("status"),
                affected_st02=data.get("affected_st02"),
                raw_file_ref=data.get("raw_file_ref"),
                edi_file_id=data.get("edi_file_id"),
                message=data.get("message"),
                apply_claim_status=data.get("apply_claim_status", True),
            )
            return success_response(
                "EDI acknowledgement applied successfully.",
                data={
                    "id": ack.id,
                    "status": ack.status,
                    "affected_st02": ack.affected_st02,
                    "updated_claim_ids": claim_ids,
                },
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Apply EDI acknowledgement failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to apply EDI acknowledgement.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
