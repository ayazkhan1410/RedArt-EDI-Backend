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

from apps.trading_partner.choices import Environment
from apps.trading_partner.models import TradingPartner
from apps.trading_partner.pagination import TradingPartnerPagination
from apps.trading_partner.serializers import (
    TradingPartnerIdSerializer,
    TradingPartnerListSerializer,
    TradingPartnerSerializer,
)

logger = logging.getLogger(__name__)

TAG = "trading_partner"

PARTNER_WRITE_EXAMPLE = OpenApiExample(
    "Sample trading partner",
    value={
        "name": "Colorado Medicaid Test TP",
        "sender_id": "REDART001",
        "receiver_id": "COHCPF",
        "environment": "TEST",
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
            OpenApiParameter(
                "environment",
                str,
                required=False,
                enum=["TEST", "PRODUCTION"],
            ),
            OpenApiParameter("search", str, required=False),
            OpenApiParameter("include_inactive", str, required=False),
        ],
        responses={200: TradingPartnerListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=TradingPartnerSerializer,
        examples=[PARTNER_WRITE_EXAMPLE],
        responses={201: TradingPartnerIdSerializer},
    ),
)
class TradingPartnerListCreateAPIView(APIView):
    def get(self, request):
        try:
            partners = TradingPartner.objects.all().order_by("-id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                partners = partners.filter(is_active=True)

            environment = request.query_params.get("environment")
            if environment:
                environment = environment.strip().upper()
                if environment not in Environment.values:
                    return error_response(
                        "Invalid environment. Use TEST or PRODUCTION.",
                        errors={"environment": ["Invalid choice."]},
                    )
                partners = partners.filter(environment=environment)

            search = request.query_params.get("search", "").strip()
            if search:
                partners = partners.filter(
                    Q(name__icontains=search)
                    | Q(sender_id__icontains=search)
                    | Q(receiver_id__icontains=search)
                )

            paginator = TradingPartnerPagination()
            page = paginator.paginate_queryset(partners, request, view=self)
            data = TradingPartnerListSerializer(page, many=True).data

            return Response(
                {
                    "success": True,
                    "message": "Trading partners retrieved successfully.",
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "data": data,
                }
            )
        except ValidationError as exc:
            return error_response(
                "Invalid pagination parameters.",
                errors=exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail},
            )
        except NotFound:
            return error_response(
                "Page not found. Use a valid page number.",
                errors={"page": ["This page does not exist."]},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error("List trading partners failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list trading partners.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = TradingPartnerSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            partner = serializer.save()
            logger.info("Created trading partner id=%s", partner.id)
            return success_response(
                "Trading partner created successfully.",
                data={"id": partner.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning("Duplicate trading partner:\n%s", traceback.format_exc())
            return error_response(
                "A trading partner with these identifiers already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error("Create trading partner failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to create trading partner.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        responses={200: TradingPartnerSerializer},
    ),
    put=extend_schema(
        tags=[TAG],
        request=TradingPartnerSerializer,
        examples=[PARTNER_WRITE_EXAMPLE],
        responses={200: TradingPartnerIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=TradingPartnerSerializer,
        examples=[PARTNER_WRITE_EXAMPLE],
        responses={200: TradingPartnerIdSerializer},
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
        responses={200: TradingPartnerIdSerializer},
    ),
)
class TradingPartnerDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            partner = get_object_or_404(TradingPartner, pk=pk)
            return success_response(
                "Trading partner retrieved successfully.",
                data=TradingPartnerSerializer(partner).data,
            )
        except Http404:
            return error_response(
                "Trading partner not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get trading partner id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to retrieve trading partner.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            partner = get_object_or_404(TradingPartner, pk=pk)
            serializer = TradingPartnerSerializer(
                partner,
                data=request.data,
                partial=partial,
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            partner = serializer.save()
            logger.info("Updated trading partner id=%s", partner.id)
            return success_response(
                "Trading partner updated successfully.",
                data={"id": partner.id},
            )
        except Http404:
            return error_response(
                "Trading partner not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            logger.warning(
                "Duplicate on update id=%s:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "A trading partner with these identifiers already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update trading partner id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update trading partner.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            partner = get_object_or_404(TradingPartner, pk=pk)
            hard_delete = request.query_params.get("hard", "").lower() in (
                "1",
                "true",
                "yes",
            )

            if hard_delete:
                partner_id = partner.id
                partner.delete()
                logger.info("Hard deleted trading partner id=%s", partner_id)
                return success_response(
                    "Trading partner permanently deleted.",
                    data={"id": partner_id},
                )

            if not partner.is_active:
                return success_response(
                    "Trading partner is already inactive.",
                    data={"id": partner.id},
                )

            partner.is_active = False
            partner.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated trading partner id=%s", partner.id)
            return success_response(
                "Trading partner deactivated successfully.",
                data={"id": partner.id},
            )
        except Http404:
            return error_response(
                "Trading partner not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete trading partner id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete trading partner.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
