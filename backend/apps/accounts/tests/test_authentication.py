from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import Role, User, UserRole


class RegistrationTests(APITestCase):
    def setUp(self):
        self.register_url = reverse(
            "accounts:register"
        )

        self.registration_data = {
            "email": "donor@example.com",
            "password": "StrongPass@123",
            "password_confirm": "StrongPass@123",
            "first_name": "Test",
            "last_name": "Donor",
            "phone_number": "9876543210",
            "role": Role.Code.DONOR,
        }

    def test_user_can_register(self):
        response = self.client.post(
            self.register_url,
            self.registration_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertTrue(
            User.objects.filter(
                email="donor@example.com"
            ).exists()
        )

        user = User.objects.get(
            email="donor@example.com"
        )

        self.assertTrue(
            user.check_password("StrongPass@123")
        )
        self.assertTrue(
            user.has_role(Role.Code.DONOR)
        )
        self.assertIn("tokens", response.data)
        self.assertIn(
            "access",
            response.data["tokens"],
        )
        self.assertIn(
            "refresh",
            response.data["tokens"],
        )

    def test_passwords_must_match(self):
        self.registration_data[
            "password_confirm"
        ] = "DifferentPass@123"

        response = self.client.post(
            self.register_url,
            self.registration_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_email_must_be_unique(self):
        User.objects.create_user(
            email="donor@example.com",
            password="StrongPass@123",
        )

        response = self.client.post(
            self.register_url,
            self.registration_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_public_cannot_register_as_admin(self):
        self.registration_data[
            "role"
        ] = Role.Code.ADMIN

        response = self.client.post(
            self.register_url,
            self.registration_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class AuthenticationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="seeker@example.com",
            password="StrongPass@123",
            first_name="Test",
            last_name="Seeker",
        )

        self.role = Role.objects.create(
            code=Role.Code.SEEKER,
            name="Blood Seeker",
        )

        UserRole.objects.create(
            user=self.user,
            role=self.role,
            is_primary=True,
        )

    def test_user_can_login(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": "seeker@example.com",
                "password": "StrongPass@123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(
            response.data["user"]["email"],
            "seeker@example.com",
        )

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": "seeker@example.com",
                "password": "WrongPassword",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_current_user_requires_authentication(self):
        response = self.client.get(
            reverse("accounts:current-user")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_authenticated_user_can_view_profile(self):
        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.get(
            reverse("accounts:current-user")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["email"],
            self.user.email,
        )

    def test_user_can_update_profile(self):
        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.patch(
            reverse("accounts:current-user"),
            {
                "first_name": "Updated",
                "phone_number": "9123456789",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.user.refresh_from_db()

        self.assertEqual(
            self.user.first_name,
            "Updated",
        )
        self.assertEqual(
            self.user.phone_number,
            "9123456789",
        )

    def test_user_can_change_password(self):
        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.post(
            reverse("accounts:change-password"),
            {
                "current_password": "StrongPass@123",
                "new_password": "NewStrongPass@123",
                "new_password_confirm": (
                    "NewStrongPass@123"
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password(
                "NewStrongPass@123"
            )
        )