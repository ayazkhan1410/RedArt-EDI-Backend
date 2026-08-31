import logging
import traceback

from django.db import IntegrityError
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
from apps.core.utils.responses import error_response, success_response
from apps.long_distance_rule.models import LongDistanceRule
from apps.long_distance_rule.serializers import (
    LongDistanceRuleIdSerializer,
    LongDistanceRuleListSerializer,
    LongDistanceRuleSerializer,
)

logger = logging.getLogger(__name__)

TAG = "long_distance_rule"

RULE_WRITE_EXAMPLE = OpenApiExample(
    "Sample long distance rule",
    value={
        "county_type": "STANDARD",
        "review_threshold": 52,
        "verification_threshold": 25,
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
            OpenApiParameter("include_inactive", str, required=False),
            OpenApiParameter(
                "county_type",
                str,
                required=False,
                enum=["STANDARD", "DESIGNATED_RURAL"],
            ),
        ],
        responses={200: LongDistanceRuleListSerializer(many=True)},
    ),
    post=extend_schema(
        tags=[TAG],
        request=LongDistanceRuleSerializer,
        examples=[RULE_WRITE_EXAMPLE],
        responses={201: LongDistanceRuleIdSerializer},
    ),
)
class LongDistanceRuleListCreateAPIView(APIView):
    def get(self, request):
        try:
            rules = LongDistanceRule.objects.all().order_by("county_type", "id")

            if request.query_params.get("include_inactive", "").lower() not in (
                "1",
                "true",
                "yes",
            ):
                rules = rules.filter(is_active=True)

            county_type = request.query_params.get("county_type", "").strip()
            if county_type:
                rules = rules.filter(county_type=county_type.upper())

            paginator = StandardPagination()
            page = paginator.paginate_queryset(rules, request, view=self)
            data = LongDistanceRuleListSerializer(page, many=True).data

            return Response(
                {
                    "success": True,
                    "message": "Long distance rules retrieved successfully.",
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
                "List long distance rules failed:\n%s",
                traceback.format_exc(),
            )
            return error_response(
                "Unable to list long distance rules.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = LongDistanceRuleSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            rule = serializer.save()
            logger.info("Created long distance rule id=%s", rule.id)
            return success_response(
                "Long distance rule created successfully.",
                data={"id": rule.id},
                status_code=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            logger.warning(
                "Duplicate long distance rule:\n%s",
                traceback.format_exc(),
            )
            return error_response(
                "A rule for this county_type already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Create long distance rule failed:\n%s",
                traceback.format_exc(),
            )
            return error_response(
                "Unable to create long distance rule.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        responses={200: LongDistanceRuleSerializer},
    ),
    put=extend_schema(
        tags=[TAG],
        request=LongDistanceRuleSerializer,
        examples=[RULE_WRITE_EXAMPLE],
        responses={200: LongDistanceRuleIdSerializer},
    ),
    patch=extend_schema(
        tags=[TAG],
        request=LongDistanceRuleSerializer,
        examples=[RULE_WRITE_EXAMPLE],
        responses={200: LongDistanceRuleIdSerializer},
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
        responses={200: LongDistanceRuleIdSerializer},
    ),
)
class LongDistanceRuleDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            rule = get_object_or_404(LongDistanceRule, pk=pk)
            return success_response(
                "Long distance rule retrieved successfully.",
                data=LongDistanceRuleSerializer(rule).data,
            )
        except Http404:
            return error_response(
                "Long distance rule not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Get long distance rule id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to retrieve long distance rule.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        try:
            rule = get_object_or_404(LongDistanceRule, pk=pk)
            serializer = LongDistanceRuleSerializer(
                rule,
                data=request.data,
                partial=partial,
            )
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)

            rule = serializer.save()
            logger.info("Updated long distance rule id=%s", rule.id)
            return success_response(
                "Long distance rule updated successfully.",
                data={"id": rule.id},
            )
        except Http404:
            return error_response(
                "Long distance rule not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            logger.warning(
                "Duplicate on update rule id=%s:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "A rule for this county_type already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.error(
                "Update long distance rule id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to update long distance rule.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            rule = get_object_or_404(LongDistanceRule, pk=pk)
            hard_delete = parse_hard_flag(request)
            denied = hard_delete_permission_error(request, hard_delete)
            if denied is not None:
                return denied

            if hard_delete:
                rule_id = rule.id
                rule.delete()
                logger.info("Hard deleted long distance rule id=%s", rule_id)
                return success_response(
                    "Long distance rule permanently deleted.",
                    data={"id": rule_id},
                )

            if not rule.is_active:
                return success_response(
                    "Long distance rule is already inactive.",
                    data={"id": rule.id},
                )

            rule.is_active = False
            rule.save(update_fields=["is_active", "updated_at"])
            logger.info("Deactivated long distance rule id=%s", rule.id)
            return success_response(
                "Long distance rule deactivated successfully.",
                data={"id": rule.id},
            )
        except Http404:
            return error_response(
                "Long distance rule not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Delete long distance rule id=%s failed:\n%s",
                pk,
                traceback.format_exc(),
            )
            return error_response(
                "Unable to delete long distance rule.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
