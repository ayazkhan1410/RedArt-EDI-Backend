import logging
import traceback

from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404
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

from apps.core.soft_delete import (
    client_error_message,
    get_active_object_or_404,
    get_api_object_or_404,
    hard_delete_permission_error,
    parse_hard_flag,
)

from apps.claim.models import BatchClaim, SubmissionBatch
from apps.claim.serializers import (
    AddClaimToBatchSerializer,
    BatchClaimIdSerializer,
    BatchClaimListSerializer,
    BatchClaimSerializer,
    SubmissionBatchIdSerializer,
    SubmissionBatchListSerializer,
    SubmissionBatchSerializer,
)
from apps.claim.utils.service import add_claim_to_batch, refresh_batch_totals
from apps.claim.utils.validators import parse_optional_int
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

BATCH_TAG = "submission_batch"
BATCH_CLAIM_TAG = "batch_claim"

BATCH_WRITE_EXAMPLE = OpenApiExample(
    "Sample submission batch",
    value={
        "batch_number": "RB-2026-10048",
        "trading_partner": 1,
        "environment": "TEST",
        "status": "READY",
        "is_active": True,
    },
    request_only=True,
)

ADD_CLAIM_EXAMPLE = OpenApiExample(
    "Add claim to batch",
    value={"claim_id": 1, "st02": "0001"},
    request_only=True,
)


@extend_schema_view(
    get=extend_schema(
        tags=[BATCH_TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("search", str, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("status", str, required=False),
            OpenApiParameter("environment", str, required=False),
            OpenApiParameter("trading_partner_id", int, required=False),
        ],
        responses={200: SubmissionBatchListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[BATCH_TAG],
        request=SubmissionBatchSerializer,
        examples=[BATCH_WRITE_EXAMPLE],
        responses={201: SubmissionBatchIdSerializer},
    ),
)
class SubmissionBatchListCreateAPIView(APIView):
    def get(self, request):
        try:
            batches = SubmissionBatch.objects.with_relations().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                batches = batches.filter(is_active=True)

            status_filter = request.query_params.get("status", "").strip()
            if status_filter:
                batches = batches.filter(status=status_filter.upper())

            environment = request.query_params.get("environment", "").strip()
            if environment:
                batches = batches.filter(environment=environment.upper())

            tp_id = parse_optional_int(
                request.query_params.get("trading_partner_id"),
                "trading_partner_id",
            )
            if tp_id:
                batches = batches.filter(trading_partner_id=tp_id)

            search = request.query_params.get("search", "").strip()
            if search:
                batches = batches.filter(
                    Q(batch_number__icontains=search)
                    | Q(trading_partner__name__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(batches, request, view=self)
            data = SubmissionBatchListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "Submission batches retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error("List submission batches failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list submission batches.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = SubmissionBatchSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            batch = serializer.save()
            logger.info("Created submission batch id=%s", batch.id)
            return success_response(
                "Submission batch created successfully.",
                data={"id": batch.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return error_response(
                "Unable to create submission batch due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Create submission batch failed:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to create submission batch.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[BATCH_TAG], responses={200: SubmissionBatchSerializer}),
    put=extend_schema(
        tags=[BATCH_TAG],
        request=SubmissionBatchSerializer,
        examples=[BATCH_WRITE_EXAMPLE],
        responses={200: SubmissionBatchIdSerializer},
    ),
    patch=extend_schema(
        tags=[BATCH_TAG],
        request=SubmissionBatchSerializer,
        examples=[BATCH_WRITE_EXAMPLE],
        responses={200: SubmissionBatchIdSerializer},
    ),
    delete=extend_schema(
        tags=[BATCH_TAG],
        parameters=[
            OpenApiParameter(
                "hard",
                str,
                required=False,
                description="Pass true to permanently delete instead of soft-deactivate.",
            ),
        ],
        responses={200: SubmissionBatchIdSerializer},
    ),
)
class SubmissionBatchDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            batch = get_active_object_or_404(
                SubmissionBatch.objects.with_relations(), pk=pk
            )
            return success_response(
                "Submission batch retrieved successfully.",
                data=SubmissionBatchSerializer(batch).data,
            )
        except Http404:
            return error_response(
                "Submission batch not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get submission batch id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to retrieve submission batch.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            batch = get_active_object_or_404(
                SubmissionBatch.objects.with_relations(), pk=pk
            )
            serializer = SubmissionBatchSerializer(
                batch, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            batch = serializer.save()
            logger.info("Updated submission batch id=%s", batch.id)
            return success_response(
                "Submission batch updated successfully.",
                data={"id": batch.id},
            )
        except Http404:
            return error_response(
                "Submission batch not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            return error_response(
                "Unable to update submission batch due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update submission batch id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update submission batch.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            batch = get_api_object_or_404(
                SubmissionBatch.objects.with_relations(), pk=pk,
                hard=hard_delete,
            )
            if hard_delete:
                batch_id = batch.id
                batch.delete()
                logger.info("Hard deleted submission batch id=%s", batch_id)
                return success_response(
                    "Submission batch permanently deleted.",
                    data={"id": batch_id},
                )
            if not batch.is_active:
                return success_response(
                    "Submission batch is already inactive.",
                    data={"id": batch.id},
                )
            batch.is_active = False
            batch.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated submission batch id=%s", batch.id)
            return success_response(
                "Submission batch deactivated successfully.",
                data={"id": batch.id},
            )
        except Http404:
            return error_response(
                "Submission batch not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete submission batch id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete submission batch.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SubmissionBatchAddClaimAPIView(APIView):
    """Add a ready claim to a batch (blocks if documents incomplete)."""

    @extend_schema(
        tags=[BATCH_TAG],
        request=AddClaimToBatchSerializer,
        examples=[ADD_CLAIM_EXAMPLE],
        responses={201: BatchClaimIdSerializer},
    )
    def post(self, request, pk):
        try:
            serializer = AddClaimToBatchSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            data = serializer.validated_data
            row = add_claim_to_batch(
                batch_id=pk,
                claim_id=data["claim_id"],
                st02=data.get("st02"),
            )
            logger.info(
                "Added claim id=%s to batch id=%s as ST02=%s",
                data["claim_id"],
                pk,
                row.st02,
            )
            return success_response(
                "Claim added to batch successfully.",
                data={"id": row.id, "st02": row.st02},
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return error_response(
                "Unable to add claim to batch due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Add claim to batch id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to add claim to batch.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(
        tags=[BATCH_CLAIM_TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("batch_id", int, required=False),
            OpenApiParameter("claim_id", int, required=False),
        ],
        responses={200: BatchClaimListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[BATCH_CLAIM_TAG],
        request=BatchClaimSerializer,
        examples=[
            OpenApiExample(
                "Sample batch claim",
                value={"batch": 1, "claim": 1, "st02": "0001", "is_active": True},
                request_only=True,
            )
        ],
        responses={201: BatchClaimIdSerializer},
    ),
)
class BatchClaimListCreateAPIView(APIView):
    def get(self, request):
        try:
            rows = BatchClaim.objects.with_relations().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                rows = rows.filter(is_active=True)

            batch_id = parse_optional_int(
                request.query_params.get("batch_id"), "batch_id"
            )
            if batch_id:
                rows = rows.filter(batch_id=batch_id)

            claim_id = parse_optional_int(
                request.query_params.get("claim_id"), "claim_id"
            )
            if claim_id:
                rows = rows.filter(claim_id=claim_id)

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            data = BatchClaimListSerializer(page, many=True).data
            return Response(
                {
                    "success": True,
                    "message": "Batch claims retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response("Validation failed.", errors=exc.detail)
        except Exception:
            logger.error("List batch claims failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list batch claims.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """Direct create still enforces readiness via add_claim_to_batch."""
        try:
            serializer = BatchClaimSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            data = serializer.validated_data
            row = add_claim_to_batch(
                batch_id=data["batch"].id,
                claim_id=data["claim"].id,
                st02=data.get("st02"),
            )
            return success_response(
                "Batch claim created successfully.",
                data={"id": row.id, "st02": row.st02},
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return error_response(
                "Unable to create batch claim due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create batch claim failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create batch claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[BATCH_CLAIM_TAG], responses={200: BatchClaimSerializer}),
    delete=extend_schema(
        tags=[BATCH_CLAIM_TAG],
        parameters=[
            OpenApiParameter(
                "hard",
                str,
                required=False,
                description="Pass true to permanently delete instead of soft-deactivate.",
            ),
        ],
        responses={200: BatchClaimIdSerializer},
    ),
)
class BatchClaimDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            row = get_active_object_or_404(BatchClaim.objects.with_relations(), pk=pk)
            return success_response(
                "Batch claim retrieved successfully.",
                data=BatchClaimSerializer(row).data,
            )
        except Http404:
            return error_response(
                "Batch claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get batch claim id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to retrieve batch claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            row = get_api_object_or_404(BatchClaim.objects.with_relations(), pk=pk, hard=hard_delete)
            batch = row.batch
            if hard_delete:
                row_id = row.id
                row.delete()
                if batch is not None:
                    refresh_batch_totals(batch)
                logger.info("Hard deleted batch claim id=%s", row_id)
                return success_response(
                    "Batch claim permanently deleted.",
                    data={"id": row_id},
                )
            if not row.is_active:
                return success_response(
                    "Batch claim is already inactive.",
                    data={"id": row.id},
                )
            row.is_active = False
            row.save(update_fields=["is_active", "updated_at"])
            if batch is not None:
                refresh_batch_totals(batch)
            logger.info("Deactivated batch claim id=%s", row.id)
            return success_response(
                "Batch claim deactivated successfully.",
                data={"id": row.id},
            )
        except Http404:
            return error_response(
                "Batch claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete batch claim id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete batch claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
