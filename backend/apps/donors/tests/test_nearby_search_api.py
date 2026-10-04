from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role, UserRole
from apps.blood_banks.models import BloodBank
from apps.donors.models import (
    DonorEligibilityAssessment,
    DonorProfile,
)
from apps.inventory.models import BloodGroup
from apps.locations.models import Location


User = get_user_model()


class NearbyDonorSearchAPITests(APITestCase):
    def setUp(self):
        self.bank_owner = User.objects.create_user(
            email="donor-search-owner@example.com",
            password="Owner@12345",
        )
        self.normal_user = User.objects.create_user(
            email="donor-search-user@example.com",
            password="User@12345",
        )
        self.staff_only = User.objects.create_user(
            email="donor-search-staff@example.com",
            password="Staff@12345",
            is_staff=True,
        )
        self.application_admin = User.objects.create_user(
            email="donor-search-admin@example.com",
            password="Admin@12345",
        )
        admin_role, _ = Role.objects.get_or_create(
            code=Role.Code.ADMIN,
            defaults={"name": Role.Code.ADMIN.label},
        )
        UserRole.objects.create(
            user=self.application_admin,
            role=admin_role,
            is_primary=True,
        )

        location = Location.objects.create(
            address_line="Donor Search Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude="21.349000",
            longitude="74.879000",
        )
        BloodBank.objects.create(
            name="Donor Search Test Bank",
            location=location,
            owner=self.bank_owner,
            source=BloodBank.Source.USER_REGISTERED,
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            ),
            is_active=True,
            is_public=True,
        )

        self.blood_group = BloodGroup.objects.create(
            code="O+",
            name="O Positive",
        )
        donor_user = User.objects.create_user(
            email="nearby-donor@example.com",
            password="Donor@12345",
        )
        self.donor = DonorProfile.objects.create(
            user=donor_user,
            blood_group=self.blood_group,
            date_of_birth=date(1995, 6, 15),
            gender=DonorProfile.Gender.PREFER_NOT_TO_SAY,
            weight_kg=Decimal("68.00"),
            phone="9000000001",
            address="Private donor address",
            city="Shirpur",
            state="Maharashtra",
            pincode="425405",
            latitude=Decimal("21.349500"),
            longitude=Decimal("74.879500"),
            is_available=True,
            medical_declaration_accepted=True,
        )
        DonorEligibilityAssessment.objects.create(
            donor=self.donor,
            is_eligible=True,
            age_at_assessment=30,
            weight_at_assessment=Decimal("68.00"),
            reasons=[],
            answers={"feeling_well": True},
        )

        self.url = reverse("donors:nearby-donor-search")
        self.query = {
            "blood_group": str(self.blood_group.id),
            "latitude": "21.349000",
            "longitude": "74.879000",
            "radius_km": "10",
        }

    def search_as(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get(self.url, self.query)

    def add_matching_donors(self, count, offset):
        users = User.objects.bulk_create(
            [
                User(
                    email=(
                        f"query-donor-{offset + index}"
                        "@example.com"
                    )
                )
                for index in range(count)
            ]
        )
        donors = DonorProfile.objects.bulk_create(
            [
                DonorProfile(
                    user=user,
                    blood_group=self.blood_group,
                    date_of_birth=date(1995, 6, 15),
                    gender=(
                        DonorProfile.Gender
                        .PREFER_NOT_TO_SAY
                    ),
                    weight_kg=Decimal("68.00"),
                    phone=f"90000{offset + index:05d}",
                    address="Private donor address",
                    city="Shirpur",
                    state="Maharashtra",
                    pincode="425405",
                    latitude=Decimal("21.349500"),
                    longitude=Decimal("74.879500"),
                    is_available=True,
                    medical_declaration_accepted=True,
                )
                for index, user in enumerate(users)
            ]
        )
        DonorEligibilityAssessment.objects.bulk_create(
            [
                DonorEligibilityAssessment(
                    donor=donor,
                    is_eligible=True,
                    age_at_assessment=30,
                    weight_at_assessment=Decimal("68.00"),
                    reasons=[],
                    answers={"feeling_well": True},
                )
                for donor in donors
            ]
        )

    def test_nearby_search_query_scaling(self):
        self.client.force_authenticate(user=self.bank_owner)
        measurements = []

        for expected_count, additional_count in (
            (1, 0),
            (10, 9),
            (50, 40),
        ):
            self.add_matching_donors(
                additional_count,
                expected_count - additional_count,
            )
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(
                    self.url,
                    self.query,
                )
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
            )
            self.assertEqual(
                response.data["count"],
                expected_count,
            )
            measurements.append(
                (expected_count, len(queries))
            )

        one_donor_queries = measurements[0][1]
        fifty_donor_queries = measurements[-1][1]
        self.assertLessEqual(
            fifty_donor_queries,
            one_donor_queries + 1,
            measurements,
        )

    def test_nearby_search_uses_latest_assessment(self):
        latest_assessment = (
            DonorEligibilityAssessment.objects.create(
                donor=self.donor,
                is_eligible=False,
                age_at_assessment=30,
                weight_at_assessment=Decimal("68.00"),
                reasons=["Temporarily ineligible"],
                answers={"feeling_well": False},
            )
        )
        DonorEligibilityAssessment.objects.filter(
            pk=latest_assessment.pk,
        ).update(
            assessed_at=timezone.now() + timedelta(seconds=1),
        )

        response = self.search_as(self.bank_owner)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["count"], 0)

    def test_nearby_donor_search_does_not_expose_email(self):
        response = self.search_as(self.bank_owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("email", response.data["results"][0])

    def test_nearby_donor_search_exposes_only_intended_contact_channel(self):
        response = self.search_as(self.bank_owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data["results"][0]
        self.assertEqual(result["phone"], self.donor.phone)
        self.assertNotIn("email", result)

    def test_nearby_donor_search_does_not_expose_sensitive_fields(self):
        response = self.search_as(self.bank_owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data["results"][0]
        for field in (
            "address",
            "latitude",
            "longitude",
            "date_of_birth",
            "weight_kg",
            "answers",
            "reasons",
        ):
            self.assertNotIn(field, result)

    def test_is_staff_only_cannot_search_donors(self):
        response = self.search_as(self.staff_only)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_application_admin_can_search_donors_without_is_staff(self):
        response = self.search_as(self.application_admin)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_bank_owner_can_search_donors_with_existing_scope(self):
        response = self.search_as(self.bank_owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_unrelated_user_cannot_bypass_donor_search_scope(self):
        response = self.search_as(self.normal_user)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
