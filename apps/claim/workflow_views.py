"""Attachment queue, dashboard, upload/download, and live submit APIs."""

import logging
import traceback

from django.db import IntegrityError
from django.http import Http404, HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.claim.models import Claim, ClaimDocument
from apps.claim.serializers import (
    AttachmentDashboardSerializer,
    AttachmentSubmissionIdSerializer,
    AttachmentSubmissionSerializer,
    BulkAttachmentReviewSerializer,
    ClaimDocumentIdSerializer,
    ClaimDocumentUploadSerializer,
    SubmitAttachmentSerializer,
)
from apps.claim.utils.attachment_service import (
    build_attachment_dashboard,
    bulk_review_attachments,
    list_attachment_queue,
    submit_claim_attachments,
    upsert_claim_document_from_upload,
)
from apps.claim.utils.document_storage import (
    download_claim_document_bytes,
    upload_claim_document_bytes,
)
from apps.claim.utils.validators import parse_optional_bool
from apps.core.pagination import StandardPagination
from apps.core.soft_delete import client_error_message, get_active_object_or_404
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

QUEUE_TAG = "attachment_queue"
DASHBOARD_TAG = "attachment_dashboard"
UPLOAD_TAG = "claim_document"


class ClaimAttachmentQueueAPIView(APIView):
    @extend_schema(
        tags=[QUEUE_TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("documents_complete", str, required=False),
            OpenApiParameter("can_submit", str, required=False),
        ],
        responses={200: dict},
    )
    def get(self, request):
        try:
            documents_complete = parse_optional_bool(
                request.query_params.get("documents_complete")
            )
            can_submit = parse_optional_bool(request.query_params.get("can_submit"))

            rows = list_attachment_queue(
                documents_complete=documents_complete,
                can_submit=can_submit,
            )
            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            return Response(
                {
                    "success": True,
                    "message": "Attachment queue retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": page,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error("Attachment queue failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list attachment queue.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClaimAttachmentDashboardAPIView(APIView):
    @extend_schema(
        tags=[DASHBOARD_TAG],
        responses={200: AttachmentDashboardSerializer},
    )
    def get(self, request):
        try:
            data = build_attachment_dashboard()
            return success_response(
                "Attachment dashboard metrics retrieved successfully.",
                data=data,
            )
        except Exception:
            logger.error("Attachment dashboard failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to build attachment dashboard.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClaimDocumentUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=[UPLOAD_TAG],
        request=ClaimDocumentUploadSerializer,
        responses={201: ClaimDocumentIdSerializer},
    )
    def post(self, request):
        try:
            serializer = ClaimDocumentUploadSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            claim = get_active_object_or_404(Claim.objects.all(), pk=serializer.validated_data["claim"])
            upload_file = serializer.validated_data["file"]
            data = upload_file.read()
            stored = upload_claim_document_bytes(
                claim_id=claim.id,
                document_type=serializer.validated_data["document_type"],
                file_name=upload_file.name,
                data=data,
                content_type=upload_file.content_type,
            )
            doc = upsert_claim_document_from_upload(
                claim=claim,
                document_type=serializer.validated_data["document_type"],
                file_name=stored["file_name"],
                document_hash=stored["document_hash"],
                blob_ref=stored["blob_ref"],
                content_type=stored["content_type"],
                file_size=stored["file_size"],
                is_signed=serializer.validated_data.get("is_signed", False),
                status=serializer.validated_data.get("status"),
                service_date=serializer.validated_data.get("service_date"),
                verification_date=serializer.validated_data.get("verification_date"),
            )
            logger.info("Uploaded claim document id=%s claim_id=%s", doc.id, claim.id)
            return success_response(
                "Claim document uploaded successfully.",
                data={"id": doc.id},
                status_code=status.HTTP_201_CREATED,
            )
        except Http404:
            return error_response(
                "Claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return error_response(
                "Unable to upload claim document due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Claim document upload failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to upload claim document.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClaimDocumentFileAPIView(APIView):
    @extend_schema(
        tags=[UPLOAD_TAG],
        responses={200: bytes},
    )
    def get(self, request, pk):
        try:
            doc = get_active_object_or_404(ClaimDocument.objects.all(), pk=pk)
            if not doc.blob_ref:
                return error_response(
                    "Document has no stored file.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            body, content_type = download_claim_document_bytes(doc.blob_ref)
            response = HttpResponse(body, content_type=content_type)
            if doc.file_name:
                response["Content-Disposition"] = f'inline; filename="{doc.file_name}"'
            return response
        except Http404:
            return error_response(
                "Claim document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return error_response(
                client_error_message(exc),
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Download claim document id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to download claim document.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        tags=["attachment_submission"],
        request=SubmitAttachmentSerializer,
        responses={201: AttachmentSubmissionIdSerializer},
    ),
)
class AttachmentSubmissionSubmitAPIView(APIView):
    """Run live/configurable attachment adapter for a claim with complete documents."""

    def post(self, request):
        try:
            serializer = SubmitAttachmentSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            data = serializer.validated_data
            submission = submit_claim_attachments(
                data["claim_id"],
                channel=data.get("channel"),
                submission_reference=data.get("submission_reference"),
                environment=data.get("environment"),
                allow_retry=data.get("allow_retry", False),
            )
            return success_response(
                "Attachment submission processed successfully.",
                data={
                    "id": submission.id,
                    "status": submission.status,
                    "submission_reference": submission.submission_reference,
                    "remote_path": submission.remote_path,
                    "payload_hash": submission.payload_hash,
                },
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return error_response(
                "Duplicate attachment transmission blocked.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Attachment submit failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to submit attachments.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AttachmentBulkReviewAPIView(APIView):
    """Batch confirm, fail, or submit attachments for multiple claims."""

    @extend_schema(
        tags=["attachment_submission"],
        request=BulkAttachmentReviewSerializer,
        responses={200: dict},
    )
    def post(self, request):
        try:
            serializer = BulkAttachmentReviewSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            result = bulk_review_attachments(serializer.validated_data["items"])
            return success_response(
                "Bulk attachment review completed.",
                data=result,
            )
        except Exception:
            logger.error("Bulk attachment review failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to process bulk attachment review.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
