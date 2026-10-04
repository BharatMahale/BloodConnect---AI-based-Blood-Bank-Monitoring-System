from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import Role, User, UserRole
from apps.blood_banks.models import (
    BloodBank,
    BloodBankVerification,
)
from apps.locations.models import Location


class BloodBankAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="StrongPass@123",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="StrongPass@123",
        )

        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPass@123",
        )

        self.application_admin = User.objects.create_user(
            email="application-admin@example.com",
            password="AdminPass@123",
        )
        self.staff_only = User.objects.create_user(
            email="staff-only@example.com",
            password="StaffPass@123",
            is_staff=True,
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

        self.location = Location.objects.create(
            address_line="Hospital Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude="21.349000",
            longitude="74.879000",
        )

        self.verified_bank = BloodBank.objects.create(
            owner=self.owner,
            location=self.location,
            name="Shirpur Blood Bank",
            category=BloodBank.Category.GOVERNMENT,
            source=BloodBank.Source.USER_REGISTERED,
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            ),
        )

    def test_public_user_can_list_blood_banks(self):
        response = self.client.get(
            reverse("blood_banks:blood-bank-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["count"],
            1,
        )

    def test_public_user_can_filter_by_city(self):
        url = reverse(
            "blood_banks:blood-bank-list"
        )

        response = self.client.get(
            url,
            {"city": "Shirpur"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["count"],
            1,
        )

    def test_public_bank_detail_does_not_expose_owner_email(self):
        response = self.client.get(
            reverse(
                "blood_banks:blood-bank-detail",
                kwargs={"slug": self.verified_bank.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("owner_email", response.data)

    def test_owner_retains_owner_email_in_bank_detail(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            reverse(
                "blood_banks:blood-bank-detail",
                kwargs={"slug": self.verified_bank.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["owner_email"], self.owner.email)

    def test_authenticated_user_can_register_bank(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.post(
            reverse("blood_banks:blood-bank-list"),
            {
                "name": "New Blood Bank",
                "category": "PRIVATE",
                "contact_number": "02563234567",
                "mobile_number": "9876543210",
                "email": "bank@example.com",
                "service_time": "24x7",
                "license_number": "TEST-LICENCE-001",
                "is_public": True,
                "location": {
                    "address_line": "Main Road",
                    "city": "Dhule",
                    "district": "Dhule",
                    "state": "Maharashtra",
                    "pincode": "424001",
                    "latitude": "20.904200",
                    "longitude": "74.774900"
                }
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        blood_bank = BloodBank.objects.get(
            name="New Blood Bank"
        )

        self.assertEqual(
            blood_bank.owner,
            self.other_user,
        )
        self.assertEqual(
            blood_bank.verification_status,
            BloodBank.VerificationStatus.PENDING,
        )
        self.assertTrue(
            blood_bank.verification_records.exists()
        )

    def test_non_owner_cannot_update_bank(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.patch(
            reverse(
                "blood_banks:blood-bank-detail",
                kwargs={
                    "slug": self.verified_bank.slug
                },
            ),
            {"service_time": "10 AM to 6 PM"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_can_update_bank(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.patch(
            reverse(
                "blood_banks:blood-bank-detail",
                kwargs={
                    "slug": self.verified_bank.slug
                },
            ),
            {"service_time": "24x7"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.verified_bank.refresh_from_db()

        self.assertEqual(
            self.verified_bank.service_time,
            "24x7",
        )

    def test_admin_can_verify_pending_bank(self):
        self.verified_bank.verification_status = (
            BloodBank.VerificationStatus.PENDING
        )
        self.verified_bank.save()

        BloodBankVerification.objects.create(
            blood_bank=self.verified_bank,
            submitted_by=self.owner,
            license_number="TEST-LICENCE-001",
        )

        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.post(
            reverse(
                "blood_banks:blood-bank-verify",
                kwargs={
                    "slug": self.verified_bank.slug
                },
            ),
            {
                "status": "APPROVED",
                "remarks": "Documents checked.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.verified_bank.refresh_from_db()

        self.assertEqual(
            self.verified_bank.verification_status,
            BloodBank.VerificationStatus.VERIFIED,
        )

        self.assertTrue(
            self.owner.has_role(
                Role.Code.BLOOD_BANK_STAFF
            )
        )

    def test_admin_role_can_verify_bank_without_is_staff(self):
        self.verified_bank.verification_status = (
            BloodBank.VerificationStatus.PENDING
        )
        self.verified_bank.save()

        self.client.force_authenticate(user=self.application_admin)

        response = self.client.post(
            reverse(
                "blood_banks:blood-bank-verify",
                kwargs={"slug": self.verified_bank.slug},
            ),
            {"status": "APPROVED", "remarks": "Admin review."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_is_staff_without_admin_role_cannot_verify_bank(self):
        self.verified_bank.verification_status = (
            BloodBank.VerificationStatus.PENDING
        )
        self.verified_bank.save()

        self.client.force_authenticate(user=self.staff_only)

        response = self.client.post(
            reverse(
                "blood_banks:blood-bank-verify",
                kwargs={"slug": self.verified_bank.slug},
            ),
            {"status": "APPROVED", "remarks": "Unauthorized review."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_normal_user_cannot_verify_bank(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            reverse(
                "blood_banks:blood-bank-verify",
                kwargs={
                    "slug": self.verified_bank.slug
                },
            ),
            {
                "status": "APPROVED",
                "remarks": "Unauthorized attempt.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
