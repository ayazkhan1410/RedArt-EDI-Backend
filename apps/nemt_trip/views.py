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
    client_error_message,
    get_active_object_or_404,
    get_api_object_or_404,
    hard_delete_permission_error,
    parse_hard_flag,
)

from apps.core.pagination import StandardPagination
from apps.core.utils.responses import error_response, success_response
from apps.nemt_trip.models import NemtTrip
from apps.nemt_trip.serializers import (
    LongDistanceCheckSerializer,
    NemtTripIdSerializer,
    NemtTripListSerializer,
    NemtTripSerializer,
)
from apps.nemt_trip.utils.service import build_long_distance_payload
from apps.nemt_trip.utils.validators import parse_optional_date, parse_optional_int

logger = logging.getLogger(__name__)

TAG = "nemt_trip"

TRIP_WRITE_EXAMPLE = OpenApiExample(
    "Sample NEMT trip",
    value={
        "patient": 1,
        "provider": 1,
        "service_date": "2026-08-30",
        "pickup": "Ali Home",
        "dropoff": "Rural Clinic",
        "one_way_miles": "78.00",
        "mileage_units": 78,
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
            OpenApiParameter("patient_id", int, required=False),
            OpenApiParameter("provider_id", int, required=False),
            OpenApiParameter("service_date_from", str, required=False),
            OpenApiParameter("service_date_to", str, required=False),
            OpenApiParameter("min_miles", str, required=False),
        ],
        responses={200: NemtTripListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=NemtTripSerializer,
        examples=[TRIP_WRITE_EXAMPLE],
        responses={201: NemtTripIdSerializer},
    ),
)
class NemtTripListCreateAPIView(APIView):
    def get(self, request):
        try:
            trips = NemtTrip.objects.with_relations().order_by(
                "-service_date", "-id"
            )

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                trips = trips.filter(is_active=True)

            patient_id = parse_optional_int(
                request.query_params.get("patient_id"),
                "patient_id",
            )
            if patient_id:
                trips = trips.filter(patient_id=patient_id)

            provider_id = parse_optional_int(
                request.query_params.get("provider_id"),
                "provider_id",
            )
            if provider_id:
                trips = trips.filter(provider_id=provider_id)

            date_from = parse_optional_date(
                request.query_params.get("service_date_from"),
                "service_date_from",
            )
            if date_from:
                trips = trips.filter(service_date__gte=date_from)

            date_to = parse_optional_date(
                request.query_params.get("service_date_to"),
                "service_date_to",
            )
            if date_to:
                trips = trips.filter(service_date__lte=date_to)

            if date_from and date_to and date_from > date_to:
                return error_response(
                    "Invalid date range.",
                    errors={
                        "service_date_from": [
                            "Must be on or before service_date_to."
                        ]
                    },
                )

            min_miles = request.query_params.get("min_miles")
            if min_miles not in (None, ""):
                try:
                    trips = trips.filter(one_way_miles__gte=min_miles)
                except (TypeError, ValueError):
                    return error_response(
                        "Invalid min_miles.",
                        errors={"min_miles": ["Must be a number."]},
                    )

            search = request.query_params.get("search", "").strip()
            if search:
                trips = trips.filter(
                    Q(pickup__icontains=search)
                    | Q(dropoff__icontains=search)
                    | Q(patient__first_name__icontains=search)
                    | Q(patient__last_name__icontains=search)
                    | Q(patient__medicaid_member_id__icontains=search)
                    | Q(provider__legal_name__icontains=search)
                    | Q(provider__billing_name__icontains=search)
                    | Q(provider__npi__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(trips, request, view=self)
            data = NemtTripListSerializer(page, many=True).data

            return Response(
                {
                    "success": True,
                    "message": "NEMT trips retrieved successfully.",
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
            logger.error("List NEMT trips failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list NEMT trips.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = NemtTripSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            trip = serializer.save()
            logger.info("Created NEMT trip id=%s", trip.id)
            return success_response(
                "NEMT trip created successfully.",
                data={"id": trip.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning("Integrity error creating trip:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create NEMT trip due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create NEMT trip failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create NEMT trip.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(tags=[TAG], responses={200: NemtTripSerializer}),
    put=extend_schema(
        tags=[TAG],
        request=NemtTripSerializer,
        examples=[TRIP_WRITE_EXAMPLE],
        responses={200: NemtTripIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=NemtTripSerializer,
        examples=[TRIP_WRITE_EXAMPLE],
        responses={200: NemtTripIdSerializer},
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
        responses={200: NemtTripIdSerializer},
    ),
)
class NemtTripDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            trip = get_active_object_or_404(NemtTrip.objects.with_relations(), pk=pk)
            return success_response(
                "NEMT trip retrieved successfully.",
                data=NemtTripSerializer(trip).data,
            )
        except Http404:
            return error_response(
                "NEMT trip not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error("Get NEMT trip id=%s failed:\n%s", pk, traceback.format_exc())
            return error_response(
                "Unable to retrieve NEMT trip.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            trip = get_active_object_or_404(NemtTrip.objects.with_relations(), pk=pk)
            serializer = NemtTripSerializer(
                trip,
                data=request.data,
                partial=partial,
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            trip = serializer.save()
            logger.info("Updated NEMT trip id=%s", trip.id)
            return success_response(
                "NEMT trip updated successfully.",
                data={"id": trip.id},
            )
        except Http404:
            return error_response(
                "NEMT trip not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            logger.warning(
                "Integrity error updating trip id=%s:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update NEMT trip due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update NEMT trip id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update NEMT trip.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            trip = get_api_object_or_404(NemtTrip.objects.with_relations(), pk=pk, hard=hard_delete)

            if hard_delete:
                trip_id = trip.id
                trip.delete()
                logger.info("Hard deleted NEMT trip id=%s", trip_id)
                return success_response(
                    "NEMT trip permanently deleted.",
                    data={"id": trip_id},
                )

            if not trip.is_active:
                return success_response(
                    "NEMT trip is already inactive.",
                    data={"id": trip.id},
                )

            trip.is_active = False
            trip.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated NEMT trip id=%s", trip.id)
            return success_response(
                "NEMT trip deactivated successfully.",
                data={"id": trip.id},
            )
        except Http404:
            return error_response(
                "NEMT trip not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete NEMT trip id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete NEMT trip.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class NemtTripLongDistanceCheckAPIView(APIView):
    """
    Preview Colorado long-distance / attachment flags for a trip
    using patient county + mileage (52/125 and 25+ rules).
    """

    @extend_schema(
        tags=[TAG],
        responses={200: LongDistanceCheckSerializer},
    )
    def get(self, request, pk):
        try:
            trip = get_active_object_or_404(NemtTrip.objects.with_relations(), pk=pk)
            payload = build_long_distance_payload(trip)
            return success_response(
                "Long-distance evaluation completed.",
                data=payload,
            )
        except Http404:
            return error_response(
                "NEMT trip not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Long-distance check for trip id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to evaluate long-distance rules.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
