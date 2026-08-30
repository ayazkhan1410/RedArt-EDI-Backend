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
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.claim.utils.validators import parse_optional_int
from apps.claim_service_line.models import ClaimServiceLine
from apps.claim_service_line.serializers import (
    ClaimServiceLineIdSerializer,
    ClaimServiceLineListSerializer,
    ClaimServiceLineSerializer,
)
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

TAG = "claim_service_line"

LINE_WRITE_EXAMPLE = OpenApiExample(
    "Sample claim service line",
    value={
        "claim": 1,
        "procedure_code": "A0100",
        "from_date": "2026-08-30",
        "to_date": "2026-08-30",
        "units": 78,
        "mileage": "78.00",
        "charge": "150.00",
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
        ],
        responses={200: ClaimServiceLineListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=ClaimServiceLineSerializer,
        examples=[LINE_WRITE_EXAMPLE],
        responses={201: ClaimServiceLineIdSerializer},
    ),
)
class ClaimServiceLineListCreateAPIView(APIView):
    def get(self, request):
        try:
            lines = ClaimServiceLine.objects.with_relations().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                lines = lines.filter(is_active=True)

            claim_id = parse_optional_int(
                request.query_params.get("claim_id"), "claim_id"
            )
            if claim_id:
                lines = lines.filter(claim_id=claim_id)

            search = request.query_params.get("search", "").strip()
            if search:
                lines = lines.filter(
                    Q(procedure_code__icontains=search)
                    | Q(claim__claim_number__icontains=search)
                    | Q(claim__external_id__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(lines, request, view=self)
            data = ClaimServiceLineListSerializer(page, many=True).data

            return Response(
                {
                    "success": True,
                    "message": "Claim service lines retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response(
                "Invalid query parameters.",
                errors=(
                    exc.detail
                    if isinstance(exc.detail, dict)
                    else {"detail": exc.detail}
                ),
            )
        except NotFound:
            return error_response(
                "Page not found. Use a valid page number.",
                errors={"page": ["This page does not exist."]},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "List claim service lines failed:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to list claim service lines.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = ClaimServiceLineSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            line = serializer.save()
            logger.info("Created claim service line id=%s", line.id)
            return success_response(
                "Claim service line created successfully.",
                data={"id": line.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning(
                "Integrity error creating service line:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to create claim service line due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Create claim service line failed:\n%s", traceback.format_exc()
            )
            return error_response(
                "Unable to create claim service line.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[TAG], responses={200: ClaimServiceLineSerializer}),
    put=extend_schema(
        tags=[TAG],
        request=ClaimServiceLineSerializer,
        examples=[LINE_WRITE_EXAMPLE],
        responses={200: ClaimServiceLineIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=ClaimServiceLineSerializer,
        examples=[LINE_WRITE_EXAMPLE],
        responses={200: ClaimServiceLineIdSerializer},
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
        responses={200: ClaimServiceLineIdSerializer},
    ),
)
class ClaimServiceLineDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            line = get_object_or_404(
                ClaimServiceLine.objects.with_relations(), pk=pk
            )
            return success_response(
                "Claim service line retrieved successfully.",
                data=ClaimServiceLineSerializer(line).data,
            )
        except Http404:
            return error_response(
                "Claim service line not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get service line id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to retrieve claim service line.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            line = get_object_or_404(
                ClaimServiceLine.objects.with_relations(), pk=pk
            )
            serializer = ClaimServiceLineSerializer(
                line, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            line = serializer.save()
            logger.info("Updated claim service line id=%s", line.id)
            return success_response(
                "Claim service line updated successfully.",
                data={"id": line.id},
            )
        except Http404:
            return error_response(
                "Claim service line not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            logger.warning(
                "Integrity error updating service line id=%s:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update claim service line due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update service line id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update claim service line.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            line = get_object_or_404(ClaimServiceLine, pk=pk)
            hard_delete = request.query_params.get("hard", "").lower() in (
                "1",
                "true",
                "yes",
            )
            if hard_delete:
                line_id = line.id
                line.delete()
                logger.info("Hard deleted service line id=%s", line_id)
                return success_response(
                    "Claim service line permanently deleted.",
                    data={"id": line_id},
                )
            if not line.is_active:
                return success_response(
                    "Claim service line is already inactive.",
                    data={"id": line.id},
                )
            line.is_active = False
            line.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated service line id=%s", line.id)
            return success_response(
                "Claim service line deactivated successfully.",
                data={"id": line.id},
            )
        except Http404:
            return error_response(
                "Claim service line not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete service line id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete claim service line.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
