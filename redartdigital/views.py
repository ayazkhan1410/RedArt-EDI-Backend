import os
from pathlib import Path

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckAPIView(APIView):
    """Liveness endpoint for load balancers / ops."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "redartdigital-edi",
                "release": os.environ.get("RENDER_GIT_COMMIT", "unknown"),
                "key_b64_present": bool(os.environ.get("HCPF_SFTP_PRIVATE_KEY_B64")),
                "key_pem_present": bool(os.environ.get("HCPF_SFTP_PRIVATE_KEY_PEM")),
                "key_file_present": Path(
                    os.environ.get(
                        "HCPF_SFTP_PRIVATE_KEY_PATH",
                        "/etc/secrets/edifecs_sftp_private_key.pem",
                    )
                ).is_file(),
            }
        )
