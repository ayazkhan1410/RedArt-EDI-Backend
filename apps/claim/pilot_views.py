"""Long-distance pilot orchestration API for RedArt backend."""

import logging
import traceback

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.claim.serializers import LongDistancePilotSerializer
from apps.claim.utils.pilot_service import run_long_distance_pilot
from apps.core.soft_delete import client_error_message
from apps.core.utils.responses import error_response, success_response

logger = logging.getLogger(__name__)

TAG = "pilot"


class LongDistancePilotAPIView(APIView):
    """
    Run Step-8 long-distance flow: attachments → batch → 837P → optional upload.
    RedArt backend calls this instead of chaining many endpoints manually.
    """

    @extend_schema(
        tags=[TAG],
        request=LongDistancePilotSerializer,
        responses={201: dict},
    )
    def post(self, request):
        try:
            serializer = LongDistancePilotSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response("Validation failed.", errors=serializer.errors)
            data = serializer.validated_data
            result = run_long_distance_pilot(
                claim_id=data["claim_id"],
                trading_partner_id=data["trading_partner_id"],
                batch_number=data.get("batch_number"),
                environment=data.get("environment"),
                submit_attachments=data.get("submit_attachments", True),
                attachment_channel=data.get("attachment_channel"),
                attachment_reference=data.get("attachment_reference"),
                queue_upload=data.get("queue_upload", False),
                upload_async=data.get("upload_async", True),
            )
            return success_response(
                "Long-distance pilot run completed.",
                data=result,
                status_code=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return error_response(client_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Long-distance pilot failed:\n%s", traceback.format_exc())
            return error_response(
                "Unable to run long-distance pilot.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
