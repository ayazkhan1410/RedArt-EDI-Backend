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
from apps.patient.models import Patient
from apps.patient.serializers import (
    PatientIdSerializer,
    PatientListSerializer,
    PatientSerializer,
)

logger = logging.getLogger(__name__)

TAG = "patient"

PATIENT_WRITE_EXAMPLE = OpenApiExample(
    "Sample patient",
    value={
        "first_name": "Ali",
        "last_name": "Khan",
        "email": "ali.khan@example.com",
        "date_of_birth": "1995-05-12",
        "medicaid_member_id": "M123456789",
        "county": "Denver",
        "is_active": True,
    },
    request_only=True,
)


def error_response(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    body = {"success": False, "message": message}
    if errors is not None:
        body["errors"] = errors
    return Response(body, status=status_code)


def success_response(message, data=None, status_code=status.HTTP_200_OK):
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return Response(body, status=status_code)


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        parameters=[
            OpenApiParameter("page", int, required=False),
            OpenApiParameter("page_size", int, required=False),
            OpenApiParameter("search", str, required=False),
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter("county", str, required=False),
        ],
        responses={200: PatientListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=PatientSerializer,
        examples=[PATIENT_WRITE_EXAMPLE],
        responses={201: PatientIdSerializer},
    ),
)
class PatientListCreateAPIView(APIView):
    def get(self, request):
        try:
            patients = Patient.objects.all().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                patients = patients.filter(is_active=True)

            county = request.query_params.get("county", "").strip()
            if county:
                patients = patients.filter(county__iexact=county)

            search = request.query_params.get("search", "").strip()
            if search:
                patients = patients.filter(
                    Q(first_name__icontains=search)
                    | Q(last_name__icontains=search)
                    | Q(medicaid_member_id__icontains=search)
                    | Q(county__icontains=search)
                    | Q(email__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(patients, request, view=self)
            data = PatientListSerializer(page, many=True).data

            return Response(
                {
                    "success": True,
                    "message": "Patients retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response(
                "Invalid pagination parameters.",
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
            logger.error("List patients failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list patients.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = PatientSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            patient = serializer.save()
            logger.info("Created patient id=%s", patient.id)
            return success_response(
                "Patient created successfully.",
                data={"id": patient.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning("Duplicate patient:\n%s", traceback.format_exc())
            return error_response(
                "A patient with this medicaid_member_id already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create patient failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create patient.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        responses={200: PatientSerializer},
    ),
    put=extend_schema(
        tags=[TAG],
        request=PatientSerializer,
        examples=[PATIENT_WRITE_EXAMPLE],
        responses={200: PatientIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=PatientSerializer,
        examples=[PATIENT_WRITE_EXAMPLE],
        responses={200: PatientIdSerializer},
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
        responses={200: PatientIdSerializer},
    ),
)
class PatientDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            patient = get_active_object_or_404(Patient, pk=pk)
            return success_response(
                "Patient retrieved successfully.",
                data=PatientSerializer(patient).data,
            )
        except Http404:
            return error_response(
                "Patient not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get patient id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to retrieve patient.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            patient = get_active_object_or_404(Patient, pk=pk)
            serializer = PatientSerializer(
                patient,
                data=request.data,
                partial=partial,
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            patient = serializer.save()
            logger.info("Updated patient id=%s", patient.id)
            return success_response(
                "Patient updated successfully.",
                data={"id": patient.id},
            )
        except Http404:
            return error_response(
                "Patient not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            logger.warning(
                "Duplicate on update patient id=%s:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "A patient with this medicaid_member_id already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update patient id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update patient.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied
            patient = get_api_object_or_404(Patient, pk=pk, hard=hard_delete)

            if hard_delete:
                patient_id = patient.id
                patient.delete()
                logger.info("Hard deleted patient id=%s", patient_id)
                return success_response(
                    "Patient permanently deleted.",
                    data={"id": patient_id},
                )

            if not patient.is_active:
                return success_response(
                    "Patient is already inactive.",
                    data={"id": patient.id},
                )

            patient.is_active = False
            patient.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated patient id=%s", patient.id)
            return success_response(
                "Patient deactivated successfully.",
                data={"id": patient.id},
            )
        except Http404:
            return error_response(
                "Patient not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete patient id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete patient.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
