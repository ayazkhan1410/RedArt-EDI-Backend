"""Import 277 acknowledgements."""

import logging
import traceback

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.core.soft_delete import client_error_message
from apps.core.utils.responses import error_response, success_response
from apps.edi.ack_views import TAG
from apps.edi.serializers import (
    EDIAcknowledgementIdSerializer,
    Import277AcknowledgementSerializer,
)
from apps.edi.utils.service import import_277_acknowledgement

logger = logging.getLogger(__name__)


class EDIAcknowledgementImport277APIView(APIView):
    """Parse raw 277 X12 claim status and persist EDIAcknowledgement."""

    @extend_schema(
        tags=[TAG],
        request=Import277AcknowledgementSerializer,
        responses={201: EDIAcknowledgementIdSerializer},
    )
    def post(self, request):
        try:
            serializer = Import277AcknowledgementSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            data = serializer.validated_data
            (ack, claim_ids), parsed = import_277_acknowledgement(
                content=data["content"],
                batch_id=data["batch_id"],
                edi_file_id=data.get("edi_file_id"),
                raw_file_ref=data.get("raw_file_ref"),
                apply_claim_status=data.get("apply_claim_status", True),
            )
            return success_response(
                "277 acknowledgement imported successfully.",
                data={
                    "id": ack.id,
                    "status": ack.status,
                    "affected_st02": ack.affected_st02,
                    "updated_claim_ids": claim_ids,
                    "parsed": {
                        "ack_type": parsed.get("ack_type"),
                        "status": parsed.get("status"),
                        "claim_statuses": parsed.get("claim_statuses"),
                        "message": parsed.get("message"),
                    },
                },
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Import 277 failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to import 277 acknowledgement.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
