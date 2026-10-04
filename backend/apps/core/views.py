from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.views import APIView

from apps.core.serializers import HealthCheckSerializer


class HealthCheckView(APIView):
    """Check whether the API and database are available."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Check API and database health",
        responses={
            HTTP_200_OK: HealthCheckSerializer,
            HTTP_503_SERVICE_UNAVAILABLE: HealthCheckSerializer,
        },
    )
    def get(self, request):
        database_available = self._check_database()

        response_data = {
            "status": "healthy" if database_available else "unhealthy",
            "service": "BloodConnect API",
            "database": (
                "connected"
                if database_available
                else "disconnected"
            ),
        }

        status_code = (
            HTTP_200_OK
            if database_available
            else HTTP_503_SERVICE_UNAVAILABLE
        )

        return Response(response_data, status=status_code)

    @staticmethod
    def _check_database():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return True
        except Exception:
            return False
