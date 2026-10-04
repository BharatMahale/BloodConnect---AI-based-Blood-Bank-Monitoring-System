from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class DashboardAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="dashboard@example.com",
            password="Dashboard@12345",
        )

    def test_public_dashboard_is_available(self):
        response = self.client.get(
            "/api/v1/dashboard/overview/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "blood_banks",
            response.data,
        )
        self.assertIn(
            "donors",
            response.data,
        )
        self.assertIn(
            "requests",
            response.data,
        )
        self.assertIn(
            "donations",
            response.data,
        )
        self.assertIn(
            "inventory",
            response.data,
        )

        self.assertEqual(
            set(response.data["inventory"]["summary"]),
            {"total_units", "available_units"},
        )

    def test_public_dashboard_contains_only_aggregate_data(self):
        response = self.client.get(
            "/api/v1/dashboard/overview/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_text = str(response.data).lower()
        for sensitive_field in (
            "email",
            "phone",
            "address",
            "owner",
            "patient",
            "reserved_units",
        ):
            self.assertNotIn(sensitive_field, response_text)

        for group in response.data["inventory"]["by_blood_group"]:
            self.assertEqual(
                set(group),
                {"blood_group", "total_units", "available_units"},
            )

    def test_personal_dashboard_requires_authentication(
        self,
    ):
        response = self.client.get(
            "/api/v1/dashboard/me/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_health_check_has_no_implementation_details(self):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {"status", "service", "database"},
        )
        self.assertNotIn("version", response.data)
        self.assertNotIn("settings", response.data)
        self.assertNotIn("traceback", response.data)

    def test_authenticated_user_can_view_dashboard(
        self,
    ):
        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            "/api/v1/dashboard/me/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["account"]["email"],
            self.user.email,
        )

        self.assertIn(
            "notifications",
            response.data,
        )
        self.assertIn(
            "my_requests",
            response.data,
        )
        self.assertIn(
            "donor",
            response.data,
        )
        self.assertIn(
            "blood_bank_management",
            response.data,
        )
