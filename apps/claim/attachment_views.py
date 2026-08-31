import logging
import traceback

from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
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

from apps.claim.choices import AttachmentSubmissionStatus
from apps.claim.models import AttachmentSubmission
from apps.claim.serializers import (
    AttachmentSubmissionIdSerializer,
    AttachmentSubmissionListSerializer,
    AttachmentSubmissionSerializer,
)
from apps.claim.utils.service import sync_claim_from_attachment_submission
from apps.claim.utils.validators import parse_optional_int
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

TAG = "attachment_submission"

WRITE_EXAMPLE = OpenApiExample(
    "Sample attachment submission",
    value={
        "claim": 1,
        "channel": "HCPF_PORTAL",
        "submission_reference": "HCPF-ATT-789",
        "status": "CONFIRMED",
        "submitted_at": "2026-08-30T15:20:00Z",
        "is_active": True,
    },
    request_only=True,
)


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("search", str, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("claim_id", int, required=False),
            OpenApiParameter("status", str, required=False),
            OpenApiParameter("channel", str, required=False),
        ],
        responses={200: AttachmentSubmissionListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=AttachmentSubmissionSerializer,
        examples=[WRITE_EXAMPLE],
        responses={201: AttachmentSubmissionIdSerializer},
    ),
)
class AttachmentSubmissionListCreateAPIView(APIView):
    def get(self, request):
        try:
            rows = AttachmentSubmission.objects.with_relations().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                rows = rows.filter(is_active=True)

            claim_id = parse_optional_int(
                request.query_params.get("claim_id"), "claim_id"
            )
            if claim_id:
                rows = rows.filter(claim_id=claim_id)

            status_filter = request.query_params.get("status", "").strip()
            if status_filter:
                rows = rows.filter(status=status_filter.upper())

            channel = request.query_params.get("channel", "").strip()
            if channel:
                rows = rows.filter(channel=channel.upper())

            search = request.query_params.get("search", "").strip()
            if search:
                rows = rows.filter(
                    Q(submission_reference__icontains=search)
                    | Q(notes__icontains=search)
                    | Q(claim__claim_number__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            data = AttachmentSubmissionListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "Attachment submissions retrieved successfully.",
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
                "List attachment submissions failed:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to list attachment submissions.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = AttachmentSubmissionSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            if (
                row.status == AttachmentSubmissionStatus.SUBMITTED
                and row.submitted_at is None
            ):
                row.submitted_at = timezone.now()
                row.save(update_fields=["submitted_at", "updated_at"])
            if (
                row.status == AttachmentSubmissionStatus.CONFIRMED
                and row.confirmed_at is None
            ):
                row.confirmed_at = timezone.now()
                fields = ["confirmed_at", "updated_at"]
                if row.submitted_at is None:
                    row.submitted_at = row.confirmed_at
                    fields.append("submitted_at")
                row.save(update_fields=fields)
            sync_claim_from_attachment_submission(row)
            logger.info("Created attachment submission id=%s", row.id)
            return success_response(
                "Attachment submission created successfully.",
                data={"id": row.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return error_response(
                "Unable to create attachment submission due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Create attachment submission failed:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to create attachment submission.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[TAG], responses={200: AttachmentSubmissionSerializer}),
    put=extend_schema(
        tags=[TAG],
        request=AttachmentSubmissionSerializer,
        examples=[WRITE_EXAMPLE],
        responses={200: AttachmentSubmissionIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=AttachmentSubmissionSerializer,
        examples=[WRITE_EXAMPLE],
        responses={200: AttachmentSubmissionIdSerializer},
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
        responses={200: AttachmentSubmissionIdSerializer},
    ),
)
class AttachmentSubmissionDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            row = get_object_or_404(
                AttachmentSubmission.objects.with_relations(), pk=pk
            )
            return success_response(
                "Attachment submission retrieved successfully.",
                data=AttachmentSubmissionSerializer(row).data,
            )
        except Http404:
            return error_response(
                "Attachment submission not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get attachment submission id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to retrieve attachment submission.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            row = get_object_or_404(
                AttachmentSubmission.objects.with_relations(), pk=pk
            )
            serializer = AttachmentSubmissionSerializer(
                row, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            row = serializer.save()
            if (
                row.status == AttachmentSubmissionStatus.SUBMITTED
                and row.submitted_at is None
            ):
                row.submitted_at = timezone.now()
                row.save(update_fields=["submitted_at", "updated_at"])
            if (
                row.status == AttachmentSubmissionStatus.CONFIRMED
                and row.confirmed_at is None
            ):
                row.confirmed_at = timezone.now()
                fields = ["confirmed_at", "updated_at"]
                if row.submitted_at is None:
                    row.submitted_at = row.confirmed_at
                    fields.append("submitted_at")
                row.save(update_fields=fields)
            sync_claim_from_attachment_submission(row)
            logger.info("Updated attachment submission id=%s", row.id)
            return success_response(
                "Attachment submission updated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "Attachment submission not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            return error_response(
                "Unable to update attachment submission due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update attachment submission id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update attachment submission.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            row = get_object_or_404(
                AttachmentSubmission.objects.with_relations(), pk=pk
            )
            hard_delete = request.query_params.get("hard", "").lower() in (
                "1",
                "true",
                "yes",
            )
            if hard_delete:
                row_id = row.id
                row.delete()
                logger.info("Hard deleted attachment submission id=%s", row_id)
                return success_response(
                    "Attachment submission permanently deleted.",
                    data={"id": row_id},
                )
            if not row.is_active:
                return success_response(
                    "Attachment submission is already inactive.",
                    data={"id": row.id},
                )
            row.is_active = False
            row.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated attachment submission id=%s", row.id)
            return success_response(
                "Attachment submission deactivated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "Attachment submission not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete attachment submission id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete attachment submission.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
