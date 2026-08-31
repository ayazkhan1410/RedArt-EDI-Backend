"""835 remittance (ERA) import + list APIs — paid / denied from CLP."""

from __future__ import annotations

import logging
import traceback

from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
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
from apps.edi.models import EDI835Remittance
from apps.edi.serializers import (
    EDI835RemittanceIdSerializer,
    EDI835RemittanceListSerializer,
    EDI835RemittanceSerializer,
    Import835RemittanceSerializer,
)
from apps.edi.utils.import_835 import import_835_remittance

logger = logging.getLogger(__name__)

TAG = "edi_835"

IMPORT_835_EXAMPLE = OpenApiExample(
    "Import 835 (paid + denied CLP)",
    value={
        "content": (
            "ISA*00*          *00*          *ZZ*SENDER         "
            "*ZZ*RECEIVER       *260101*1200*^*00501*000000905*0*P*:~"
            "GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~"
            "ST*835*0001~"
            "BPR*I*14.90*C*CHK************20260115~"
            "TRN*1*TRACE123456*1234567890~"
            "CLP*TESTCLAIM0001*1*14.90*14.90*0*MC*PAYERCTRL1*11~"
            "CAS*CO*45*0~"
            "CLP*UNKNOWNCLAIM*4*20.00*0*0*MC*PAYERCTRL2*11~"
            "SE*8*0001~"
            "GE*1*1~"
            "IEA*1*000000905~"
        ),
        "raw_file_ref": "manual-paste",
        "apply_claim_status": True,
    },
    request_only=True,
)


@extend_schema_view(
    get=extend_schema(
        tags=[TAG],
        summary="List imported 835 remittances",
        responses={200: EDI835RemittanceListSerializer(many=True)},
    ),
)
class EDI835RemittanceListAPIView(APIView):
    def get(self, request):
        try:
            rows = EDI835Remittance.objects.filter(is_active=True).order_by("-id")
            paginator = StandardPagination()
            page = paginator.paginate_queryset(rows, request, view=self)
            data = EDI835RemittanceListSerializer(page, many=True).data
            return paginator.get_paginated_response(data)
        except Exception:
            logger.error("List 835 remittances failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to list 835 remittances.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(
    tags=[TAG],
    summary="Import 835 ERA (sets Claim PAID / DENIED from CLP)",
    description=(
        "Paste raw X12 835 content. Matches CLP01 to Claim.claim_number "
        "(or external_id). CLP02=4 → DENIED; processed-as codes with payment>0 "
        "→ PAID. Idempotent on content SHA-256. Never confuses 999 with payment."
    ),
    request=Import835RemittanceSerializer,
    examples=[IMPORT_835_EXAMPLE],
    responses={201: EDI835RemittanceIdSerializer},
)
class EDI835RemittanceImportAPIView(APIView):
    def post(self, request):
        try:
            serializer = Import835RemittanceSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            data = serializer.validated_data
            remittance, claim_ids, meta = import_835_remittance(
                content=data["content"],
                raw_file_ref=data.get("raw_file_ref"),
                apply_claim_status=data.get("apply_claim_status", True),
            )
            remittance = (
                EDI835Remittance.objects.with_relations()
                .filter(pk=remittance.pk)
                .first()
            )
            payload = EDI835RemittanceSerializer(remittance).data
            payload["updated_claim_ids"] = claim_ids
            payload["idempotent"] = bool(meta.get("idempotent"))
            http_status = (
                status.HTTP_200_OK
                if meta.get("idempotent")
                else status.HTTP_201_CREATED
            )
            return success_response(
                (
                    "835 remittance already imported (idempotent)."
                    if meta.get("idempotent")
                    else "835 remittance imported successfully."
                ),
                data=payload,
                status_code=http_status,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Import 835 remittance failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to import 835 remittance.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(
    tags=[TAG],
    summary="Get one 835 remittance with CLP lines",
    responses={200: EDI835RemittanceSerializer},
)
class EDI835RemittanceDetailAPIView(APIView):
    def get(self, request, pk):
        try:
            row = get_active_object_or_404(
                EDI835Remittance.objects.with_relations().filter(is_active=True),
                pk=pk,
            )
            return success_response(
                "835 remittance retrieved.",
                data=EDI835RemittanceSerializer(row).data,
            )
        except Exception as exc:
            from django.http import Http404

            if isinstance(exc, Http404):
                raise
            logger.error("Get 835 remittance failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to retrieve 835 remittance.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
