"""Claim / batch validate + status endpoints for RedArt handoff."""

from __future__ import annotations

import logging
import traceback

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.claim.models import Claim, SubmissionBatch
from apps.claim.utils.service import (
    get_batch_status_payload,
    get_claim_status_payload,
    validate_claim_for_edi,
)
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

TAG = "claim"
BATCH_TAG = "claim"


class ClaimValidateAPIView(APIView):
    """
    POST /api/v1/claims/{id}/validate/
    Returns handoff-shaped {ready, errors[]} plus claim status context.
    """

    @extend_schema(
        tags=[TAG],
        request=None,
        examples=[
            OpenApiExample(
                "Ready",
                value={
                    "success": True,
                    "message": "Claim validation complete.",
                    "data": {
                        "ready": True,
                        "errors": [],
                        "warnings": [],
                        "claim_id": 1,
                        "status": "READY_FOR_837P",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Not ready",
                value={
                    "success": True,
                    "message": "Claim validation complete.",
                    "data": {
                        "ready": False,
                        "errors": ["Medicaid member ID missing"],
                        "claim_id": 1,
                        "status": "DOCUMENTS_REQUIRED",
                    },
                },
                response_only=True,
            ),
        ],
        responses={200: dict},
    )
    def post(self, request, pk):
        try:
            claim = get_object_or_404(Claim.objects.with_relations(), pk=pk)
            data = validate_claim_for_edi(claim, update_status=True)
            return success_response("Claim validation complete.", data=data)
        except Http404:
            return error_response(
                "Claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Validate claim id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to validate claim.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClaimStatusAPIView(APIView):
    """GET /api/v1/claims/{id}/status/ — EDI-facing status for RedArt UI."""

    @extend_schema(tags=[TAG], responses={200: dict})
    def get(self, request, pk):
        try:
            claim = get_object_or_404(Claim.objects.with_relations(), pk=pk)
            data = get_claim_status_payload(claim)
            return success_response("Claim status retrieved.", data=data)
        except Http404:
            return error_response(
                "Claim not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error(
                "Claim status id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to retrieve claim status.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SubmissionBatchStatusAPIView(APIView):
    """GET /api/v1/submission-batches/{id}/status/"""

    @extend_schema(tags=[BATCH_TAG], responses={200: dict})
    def get(self, request, pk):
        try:
            batch = get_object_or_404(
                SubmissionBatch.objects.select_related("trading_partner"),
                pk=pk,
            )
            data = get_batch_status_payload(batch)
            return success_response("Batch status retrieved.", data=data)
        except Http404:
            return error_response(
                "Batch not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error(
                "Batch status id=%s failed:\n%s", pk, traceback.format_exc()
            )
            return error_response(
                "Unable to retrieve batch status.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
