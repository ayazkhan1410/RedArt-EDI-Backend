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

from apps.core.soft_delete import hard_delete_permission_error, parse_hard_flag

from apps.core.pagination import StandardPagination
from apps.provider_billing_profile.models import ProviderBillingProfile
from apps.provider_billing_profile.serializers import (
    ProviderBillingProfileIdSerializer,
    ProviderBillingProfileListSerializer,
    ProviderBillingProfileSerializer,
)

logger = logging.getLogger(__name__)

TAG = "provider_billing_profile"

PROFILE_WRITE_EXAMPLE = OpenApiExample(
    "Sample provider billing profile",
    value={
        "legal_name": "WALLA INVESTMENT LLC",
        "billing_name": "WALLA INVESTMENT LLC",
        "npi": "1750058525",
        "taxonomy_code": "343900000X",
        "location_id": "9000201481",
        "medicaid_provider_id": "CO123456",
        "revalidation_date": "2029-11-25",
        "address_line_1": "100 Main St",
        "address_line_2": "Suite 2",
        "city": "Denver",
        "state": "CO",
        "zip": "80202",
        "country": "US",
        "phone": "3035550100",
        "email": "billing@example.com",
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
            OpenApiParameter("state", str, required=False),
        ],
        responses={200: ProviderBillingProfileListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=ProviderBillingProfileSerializer,
        examples=[PROFILE_WRITE_EXAMPLE],
        responses={201: ProviderBillingProfileIdSerializer},
    ),
)
class ProviderBillingProfileListCreateAPIView(APIView):
    def get(self, request):
        try:
            profiles = ProviderBillingProfile.objects.all().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                profiles = profiles.filter(is_active=True)

            state = request.query_params.get("state", "").strip()
            if state:
                profiles = profiles.filter(state__iexact=state)

            search = request.query_params.get("search", "").strip()
            if search:
                profiles = profiles.filter(
                    Q(legal_name__icontains=search)
                    | Q(billing_name__icontains=search)
                    | Q(npi__icontains=search)
                    | Q(location_id__icontains=search)
                    | Q(medicaid_provider_id__icontains=search)
                    | Q(city__icontains=search)
                    | Q(email__icontains=search)
                )

            paginator = StandardPagination()
            page = paginator.paginate_queryset(profiles, request, view=self)
            data = ProviderBillingProfileListSerializer(page, many=True).data

            return Response(
                {
                    "success": True,
                    "message": "Provider billing profiles retrieved successfully.",
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
            logger.error(
                "List provider billing profiles failed:\n%s",
                traceback.format_exc(),
            )
            return error_response(
                "Unable to list provider billing profiles.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = ProviderBillingProfileSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            profile = serializer.save()
            logger.info("Created provider billing profile id=%s", profile.id)
            return success_response(
                "Provider billing profile created successfully.",
                data={"id": profile.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning(
                "Integrity error creating provider billing profile:\n%s",
                traceback.format_exc(),
            )
            return error_response(
                "Unable to create provider billing profile due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Create provider billing profile failed:\n%s",
                traceback.format_exc(),
            )
            return error_response(
                "Unable to create provider billing profile.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        responses={200: ProviderBillingProfileSerializer},
    ),
    put=extend_schema(
        tags=[TAG],
        request=ProviderBillingProfileSerializer,
        examples=[PROFILE_WRITE_EXAMPLE],
        responses={200: ProviderBillingProfileIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=ProviderBillingProfileSerializer,
        examples=[PROFILE_WRITE_EXAMPLE],
        responses={200: ProviderBillingProfileIdSerializer},
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
        responses={200: ProviderBillingProfileIdSerializer},
    ),
)
class ProviderBillingProfileDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            profile = get_object_or_404(ProviderBillingProfile, pk=pk)
            return success_response(
                "Provider billing profile retrieved successfully.",
                data=ProviderBillingProfileSerializer(profile).data,
            )
        except Http404:
            return error_response(
                "Provider billing profile not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get provider billing profile id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to retrieve provider billing profile.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            profile = get_object_or_404(ProviderBillingProfile, pk=pk)
            serializer = ProviderBillingProfileSerializer(
                profile,
                data=request.data,
                partial=partial,
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            profile = serializer.save()
            logger.info("Updated provider billing profile id=%s", profile.id)
            return success_response(
                "Provider billing profile updated successfully.",
                data={"id": profile.id},
            )
        except Http404:
            return error_response(
                "Provider billing profile not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            logger.warning(
                "Integrity error updating provider billing profile id=%s:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update provider billing profile due to a conflict.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update provider billing profile id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update provider billing profile.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            profile = get_object_or_404(ProviderBillingProfile, pk=pk)
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied

            if hard_delete:
                profile_id = profile.id
                profile.delete()
                logger.info("Hard deleted provider billing profile id=%s", profile_id)
                return success_response(
                    "Provider billing profile permanently deleted.",
                    data={"id": profile_id},
                )

            if not profile.is_active:
                return success_response(
                    "Provider billing profile is already inactive.",
                    data={"id": profile.id},
                )

            profile.is_active = False
            profile.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated provider billing profile id=%s", profile.id)
            return success_response(
                "Provider billing profile deactivated successfully.",
                data={"id": profile.id},
            )
        except Http404:
            return error_response(
                "Provider billing profile not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete provider billing profile id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete provider billing profile.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
