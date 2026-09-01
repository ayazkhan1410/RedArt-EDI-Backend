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
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.soft_delete import (
    filter_active_for_list,
    client_error_message,
    get_active_object_or_404,
    get_api_object_or_404,
    hard_delete_permission_error,
    parse_hard_flag,
)

from apps.claim.models import Claim
from apps.claim.serializers import (
    ClaimIdSerializer,
    ClaimListSerializer,
    ClaimSerializer,
    CreateClaimFromTripSerializer,
)
from apps.claim.utils.service import create_claim_from_trip
from apps.claim.utils.validators import (
    parse_optional_bool,
    parse_optional_int,
)
from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

TAG = "claim"

CLAIM_WRITE_EXAMPLE = OpenApiExample(
    "Sample claim",
    value={
        "claim_number": "C001",
        "external_id": "TRIP-1001",
        "trip": 1,
        "diagnosis_code": "R68.89",
        "place_of_service": "41",
        "total_charge": "150.00",
        "status": "DOCUMENTS_REQUIRED",
        "attachment_required": True,
        "attachment_route": "HCPF_APPROVED_CHANNEL",
        "attachment_status": "PENDING",
        "is_active": True,
    },
    request_only=True,
)

FROM_TRIP_EXAMPLE = OpenApiExample(
    "Create claim from trip",
    value={
        "trip_id": 1,
        "claim_number": "C001",
        "external_id": "TRIP-1001",
        "diagnosis_code": "R68.89",
        "place_of_service": "41",
        "procedure_code": "A0100",
        "create_service_line": True,
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
            OpenApiParameter("status", str, required=False),
            OpenApiParameter("trip_id", int, required=False),
            OpenApiParameter("attachment_required", str, required=False),
        ],
        responses={200: ClaimListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=ClaimSerializer,
        examples=[CLAIM_WRITE_EXAMPLE],
        responses={201: ClaimIdSerializer},
    ),
)
class ClaimListCreateAPIView(APIView):
    def get(self, request):
        try:
            claims = Claim.objects.with_relations().order_by("-id")

            claims = filter_active_for_list(request, claims)

            status_filter = request.query_params.get("status", "").strip()
            if status_filter:
                claims = claims.filter(status=status_filter.upper())

            trip_id = parse_optional_int(
                request.query_params.get("trip_id"), "trip_id"
            )
            if trip_id:
                claims = claims.filter(trip_id=trip_id)

            attachment_required = parse_optional_bool(
                request.query_params.get("attachment_required")
            )
            if attachment_required is not None:
                claims = claims.filter(attachment_required=attachment_required)

            search = request.query_params.get("search", "").strip()
            if search:
                claims = claims.filter(
                    Q(claim_number__icontains=search)
                    | Q(external_id__icontains=search)
                    | Q(diagnosis_code__icontains=search)
                    | Q(trip__patient__medicaid_member_id__icontains=search)
                    | Q(trip__patient__first_name__icontains=search)
                    | Q(trip__patient__last_name__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(claims, request, view=self)
            data = ClaimListSerializer(page, many=True).data

            return Response(
                {
                    "success": True,
                    "message": "Claims retrieved successfully.",
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
            logger.error("List claims failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list claims.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = ClaimSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            claim = serializer.save()
            logger.info("Created claim id=%s", claim.id)
            return success_response(
                "Claim created successfully.",
                data={"id": claim.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning("Integrity error creating claim:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create claim due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create claim failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[TAG], responses={200: ClaimSerializer}),
    put=extend_schema(
        tags=[TAG],
        request=ClaimSerializer,
        examples=[CLAIM_WRITE_EXAMPLE],
        responses={200: ClaimIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=ClaimSerializer,
        examples=[CLAIM_WRITE_EXAMPLE],
        responses={200: ClaimIdSerializer},
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
        responses={200: ClaimIdSerializer},
    ),
)
class ClaimDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            claim = get_active_object_or_404(Claim.objects.with_relations(), pk=pk)
            return success_response(
                "Claim retrieved successfully.",
                data=ClaimSerializer(claim).data,
            )
        except Http404:
            return error_response(
                "Claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error("Get claim id=%s failed:\n%s", pk, traceback.format_exc())
            return error_response(
                "Unable to retrieve claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            claim = get_active_object_or_404(Claim.objects.with_relations(), pk=pk)
            serializer = ClaimSerializer(
                claim, data=request.data, partial=partial
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            claim = serializer.save()
            logger.info("Updated claim id=%s", claim.id)
            return success_response(
                "Claim updated successfully.",
                data={"id": claim.id},
            )
        except Http404:
            return error_response(
                "Claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            logger.warning(
                "Integrity error updating claim id=%s:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update claim due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update claim id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to update claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            claim = get_api_object_or_404(Claim.objects.with_relations(), pk=pk, hard=hard_delete)
            if hard_delete:
                claim_id = claim.id
                claim.delete()
                logger.info("Hard deleted claim id=%s", claim_id)
                return success_response(
                    "Claim permanently deleted.",
                    data={"id": claim_id},
                )
            if not claim.is_active:
                return success_response(
                    "Claim is already inactive.",
                    data={"id": claim.id},
                )
            claim.is_active = False
            claim.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated claim id=%s", claim.id)
            return success_response(
                "Claim deactivated successfully.",
                data={"id": claim.id},
            )
        except Http404:
            return error_response(
                "Claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete claim id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to delete claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClaimFromTripAPIView(APIView):
    """Create claim (+ optional service line) from trip and apply long-distance flags."""

    @extend_schema(
        tags=[TAG],
        request=CreateClaimFromTripSerializer,
        examples=[FROM_TRIP_EXAMPLE],
        responses={201: ClaimIdSerializer},
    )
    def post(self, request):
        try:
            serializer = CreateClaimFromTripSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            data = serializer.validated_data
            claim, line = create_claim_from_trip(
                trip_id=data["trip_id"],
                claim_number=data.get("claim_number"),
                external_id=data.get("external_id"),
                diagnosis_code=data.get("diagnosis_code"),
                place_of_service=data.get("place_of_service"),
                procedure_code=data.get("procedure_code") or "A0100",
                create_service_line=data.get("create_service_line", True),
            )
            payload = {"id": claim.id}
            if line is not None:
                payload["service_line_id"] = line.id
            logger.info(
                "Created claim id=%s from trip id=%s",
                claim.id,
                data["trip_id"],
            )
            return success_response(
                "Claim created from trip successfully.",
                data=payload,
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            logger.warning(
                "Integrity error create-from-trip:\n%s", traceback.format_exc()
            )
            return error_response(
                "A claim already exists for this trip.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create claim from trip failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create claim from trip.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
