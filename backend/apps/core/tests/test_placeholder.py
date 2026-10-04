from django.test import TestCase
from django.urls import reverse
from rest_framework import status


class HealthCheckTests(TestCase):
    def test_health_check_returns_success(self):
        response = self.client.get(
            reverse("core:health-check"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.json()["status"],
            "healthy",
        )
        self.assertEqual(
            response.json()["database"],
            "connected",
        )