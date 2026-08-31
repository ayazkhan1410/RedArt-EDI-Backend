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

from apps.core.soft_delete import hard_delete_permission_error, parse_hard_flag

from apps.claim.models import Claim, ClaimDocument
from apps.claim.serializers import (
    ClaimDocumentIdSerializer,
    ClaimDocumentListSerializer,
    ClaimDocumentSerializer,
)
from apps.claim.utils.service import sync_claim_document_status
from apps.claim.utils.validators import parse_optional_int
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

TAG = "claim_document"

DOC_WRITE_EXAMPLE = OpenApiExample(
    "Sample claim document",
    value={
        "claim": 1,
        "document_type": "STANDARD_TRIP_LOG",
        "file_name": "trip_log_C001.pdf",
        "document_hash": "HASH111",
        "is_signed": True,
        "status": "COMPLETE",
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
            OpenApiParameter("document_type", str, required=False),
            OpenApiParameter("status", str, required=False),
        ],
        responses={200: ClaimDocumentListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=ClaimDocumentSerializer,
        examples=[DOC_WRITE_EXAMPLE],
        responses={201: ClaimDocumentIdSerializer},
    ),
)
class ClaimDocumentListCreateAPIView(APIView):
    def get(self, request):
        try:
            docs = ClaimDocument.objects.with_relations().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                docs = docs.filter(is_active=True)

            claim_id = parse_optional_int(
                request.query_params.get("claim_id"), "claim_id"
            )
            if claim_id:
                docs = docs.filter(claim_id=claim_id)

            document_type = request.query_params.get("document_type", "").strip()
            if document_type:
                docs = docs.filter(document_type=document_type.upper())

            status_filter = request.query_params.get("status", "").strip()
            if status_filter:
                docs = docs.filter(status=status_filter.upper())

            search = request.query_params.get("search", "").strip()
            if search:
                docs = docs.filter(
                    Q(file_name__icontains=search)
                    | Q(document_hash__icontains=search)
                    | Q(claim__claim_number__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(docs, request, view=self)
            data = ClaimDocumentListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "Claim documents retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error("List claim documents failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list claim documents.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = ClaimDocumentSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            doc = serializer.save()
            if doc.claim_id:
                sync_claim_document_status(doc.claim)
            logger.info("Created claim document id=%s", doc.id)
            return success_response(
                "Claim document created successfully.",
                data={"id": doc.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning(
                "Integrity error creating claim document:\n%s",
                traceback.format_exc(),
            )
            return error_response(
                "Unable to create claim document due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create claim document failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create claim document.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[TAG], responses={200: ClaimDocumentSerializer}),
    put=extend_schema(
        tags=[TAG],
        request=ClaimDocumentSerializer,
        examples=[DOC_WRITE_EXAMPLE],
        responses={200: ClaimDocumentIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=ClaimDocumentSerializer,
        examples=[DOC_WRITE_EXAMPLE],
        responses={200: ClaimDocumentIdSerializer},
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
        responses={200: ClaimDocumentIdSerializer},
    ),
)
class ClaimDocumentDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            doc = get_object_or_404(ClaimDocument.objects.with_relations(), pk=pk)
            return success_response(
                "Claim document retrieved successfully.",
                data=ClaimDocumentSerializer(doc).data,
            )
        except Http404:
            return error_response(
                "Claim document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get claim document id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to retrieve claim document.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            doc = get_object_or_404(ClaimDocument.objects.with_relations(), pk=pk)
            serializer = ClaimDocumentSerializer(
                doc, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            doc = serializer.save()
            if doc.claim_id:
                sync_claim_document_status(doc.claim)
            logger.info("Updated claim document id=%s", doc.id)
            return success_response(
                "Claim document updated successfully.",
                data={"id": doc.id},
            )
        except Http404:
            return error_response(
                "Claim document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            return error_response(
                "Unable to update claim document due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update claim document id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update claim document.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            doc = get_object_or_404(ClaimDocument.objects.with_relations(), pk=pk)
            claim = doc.claim
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            if hard_delete:
                doc_id = doc.id
                doc.delete()
                if claim is not None:
                    sync_claim_document_status(claim)
                logger.info("Hard deleted claim document id=%s", doc_id)
                return success_response(
                    "Claim document permanently deleted.",
                    data={"id": doc_id},
                )
            if not doc.is_active:
                return success_response(
                    "Claim document is already inactive.",
                    data={"id": doc.id},
                )
            doc.is_active = False
            doc.save(update_fields=["is_active", "updated_at"])
            if claim is not None:
                sync_claim_document_status(claim)
            logger.info("Deactivated claim document id=%s", doc.id)
            return success_response(
                "Claim document deactivated successfully.",
                data={"id": doc.id},
            )
        except Http404:
            return error_response(
                "Claim document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete claim document id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete claim document.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClaimDocumentStatusAPIView(APIView):
    """Return / refresh document completeness for a claim."""

    @extend_schema(tags=[TAG], responses={200: dict})
    def get(self, request, pk):
        try:
            claim = get_object_or_404(Claim.objects.all(), pk=pk)
            snapshot = sync_claim_document_status(claim)
            claim.refresh_from_db()
            return success_response(
                "Claim document status evaluated.",
                data={
                    "claim_id": claim.id,
                    "claim_status": claim.status,
                    **snapshot,
                },
            )
        except Http404:
            return error_response(
                "Claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Claim document status id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to evaluate claim document status.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
