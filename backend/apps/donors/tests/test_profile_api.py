from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APITestCase

from apps.donors.models import DonorProfile
from apps.inventory.models import BloodGroup


User = get_user_model()


class DonorProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="donor-api@example.com",
            password="Donor@12345",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Other@12345",
        )

        self.blood_group = BloodGroup.objects.create(
            name="A Positive",
        )

        self.profile_data = {
            "blood_group": str(self.blood_group.id),
            "date_of_birth": "2002-05-20",
            "gender": "MALE",
            "weight_kg": "65.00",
            "phone": "9876543210",
            "address": "Shirpur",
            "city": "Shirpur",
            "state": "Maharashtra",
            "pincode": "425405",
            "latitude": "21.349500",
            "longitude": "74.880200",
            "last_donation_date": None,
            "is_available": True,
            "medical_declaration_accepted": True,
        }

    def test_anonymous_user_cannot_access_profile(self):
        response = self.client.get(
            "/api/v1/donors/me/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_authenticated_user_can_create_profile(self):
        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.post(
            "/api/v1/donors/me/",
            self.profile_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertTrue(
            DonorProfile.objects.filter(
                user=self.user
            ).exists()
        )

    def test_user_cannot_create_duplicate_profile(self):
        DonorProfile.objects.create(
            user=self.user,
            blood_group=self.blood_group,
            date_of_birth=date(2002, 5, 20),
            gender=DonorProfile.Gender.MALE,
            weight_kg=Decimal("65.00"),
            phone="9876543210",
            address="Shirpur",
            city="Shirpur",
            state="Maharashtra",
            pincode="425405",
            is_available=True,
            medical_declaration_accepted=True,
        )

        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.post(
            "/api/v1/donors/me/",
            self.profile_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_user_can_view_own_profile(self):
        DonorProfile.objects.create(
            user=self.user,
            blood_group=self.blood_group,
            date_of_birth=date(2002, 5, 20),
            gender=DonorProfile.Gender.MALE,
            weight_kg=Decimal("65.00"),
            phone="9876543210",
            address="Shirpur",
            city="Shirpur",
            state="Maharashtra",
            pincode="425405",
            is_available=True,
            medical_declaration_accepted=True,
        )

        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.get(
            "/api/v1/donors/me/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["email"],
            self.user.email,
        )

    def test_user_can_update_availability(self):
        donor = DonorProfile.objects.create(
            user=self.user,
            blood_group=self.blood_group,
            date_of_birth=date(2002, 5, 20),
            gender=DonorProfile.Gender.MALE,
            weight_kg=Decimal("65.00"),
            phone="9876543210",
            address="Shirpur",
            city="Shirpur",
            state="Maharashtra",
            pincode="425405",
            is_available=True,
            medical_declaration_accepted=True,
        )

        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.patch(
            "/api/v1/donors/me/",
            {
                "is_available": False,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        donor.refresh_from_db()

        self.assertFalse(donor.is_available)

    def test_user_without_profile_receives_not_found(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.get(
            "/api/v1/donors/me/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )