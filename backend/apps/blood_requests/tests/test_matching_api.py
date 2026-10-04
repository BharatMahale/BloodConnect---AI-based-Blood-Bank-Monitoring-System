from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from apps.blood_banks.models import BloodBank
from apps.blood_requests.models import (
    BloodRequest,
    BloodRequestBankAssignment,
)
from apps.blood_requests.services import (
    create_blood_request,
    transition_blood_request,
)
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
)
from apps.locations.models import Location


User = get_user_model()


class BloodBankMatchingAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_inventory_reference",
            verbosity=0,
        )

        cls.requester = User.objects.create_user(
            email="matching-user@example.com",
            password="Requester@12345",
        )

        cls.other_user = User.objects.create_user(
            email="matching-other@example.com",
            password="Other@12345",
        )

        cls.admin = User.objects.create_user(
            email="matching-admin@example.com",
            password="Admin@12345",
        )

        cls.admin.is_staff = True
        cls.admin.is_superuser = True
        cls.admin.save(
            update_fields=[
                "is_staff",
                "is_superuser",
            ]
        )

        cls.blood_group = BloodGroup.objects.get(
            name="O Positive"
        )

        cls.component = BloodComponent.objects.get(
            name="Whole Blood"
        )

        cls.full_bank = cls.create_bank(
            name="Full Availability Bank",
            latitude="21.350000",
            longitude="74.880000",
        )

        cls.partial_bank = cls.create_bank(
            name="Partial Availability Bank",
            latitude="21.370000",
            longitude="74.890000",
        )

        cls.no_stock_bank = cls.create_bank(
            name="No Stock Bank",
            latitude="21.375000",
            longitude="74.895000",
        )

        cls.distant_bank = cls.create_bank(
            name="Distant Availability Bank",
            latitude="20.904200",
            longitude="74.774900",
        )

        cls.unverified_bank = cls.create_bank(
            name="Unverified Bank",
            latitude="21.351000",
            longitude="74.881000",
            verification_status=(
                BloodBank.VerificationStatus.PENDING
            ),
        )

        # Four available units:
        # total 5 - reserved 1 = 4
        BloodInventory.objects.create(
            blood_bank=cls.full_bank,
            blood_group=cls.blood_group,
            component=cls.component,
            total_units=5,
            reserved_units=1,
        )

        # One available unit:
        # total 2 - reserved 1 = 1
        BloodInventory.objects.create(
            blood_bank=cls.partial_bank,
            blood_group=cls.blood_group,
            component=cls.component,
            total_units=2,
            reserved_units=1,
        )

        BloodInventory.objects.create(
            blood_bank=cls.distant_bank,
            blood_group=cls.blood_group,
            component=cls.component,
            total_units=10,
            reserved_units=0,
        )

    @classmethod
    def create_bank(
        cls,
        *,
        name,
        latitude,
        longitude,
        verification_status=None,
    ):
        location = Location.objects.create(
            address_line=f"{name} Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude=latitude,
            longitude=longitude,
        )

        return BloodBank.objects.create(
            name=name,
            location=location,
            source=(
                BloodBank.Source.DIRECTORY_IMPORT
            ),
            verification_status=(
                verification_status
                or BloodBank.VerificationStatus
                .DIRECTORY_IMPORTED
            ),
            is_active=True,
            is_public=True,
        )

    def setUp(self):
        self.blood_request = (
            create_blood_request(
                requester=self.requester,
                request_data={
                    "blood_bank": None,
                    "blood_group": self.blood_group,
                    "component": self.component,
                    "patient_name": (
                        "Matching Test Patient"
                    ),
                    "units_required": 3,
                    "hospital_name": (
                        "Matching Test Hospital"
                    ),
                    "hospital_address": (
                        "Main Road, Shirpur"
                    ),
                    "hospital_latitude": (
                        "21.349000"
                    ),
                    "hospital_longitude": (
                        "74.879000"
                    ),
                    "contact_phone": "9876543210",
                    "required_date": (
                        timezone.localdate()
                        + timedelta(days=1)
                    ),
                    "urgency": (
                        BloodRequest.Urgency.EMERGENCY
                    ),
                    "additional_information": (
                        "Matching API test."
                    ),
                },
            )
        )

        self.suggestions_url = reverse(
            (
                "blood_requests:"
                "blood-request-suggested-banks"
            ),
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

        self.assign_url = reverse(
            (
                "blood_requests:"
                "blood-request-assign-bank"
            ),
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

        self.assignment_history_url = reverse(
            (
                "blood_requests:"
                "blood-request-assignment-history"
            ),
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user
        )

    def test_authentication_is_required(
        self,
    ):
        response = self.client.get(
            self.suggestions_url
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_requester_receives_ranked_suggestions(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.suggestions_url,
            {
                "radius_km": 10,
                "limit": 10,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        results = response.data["results"]

        self.assertEqual(
            len(results),
            3,
        )

        self.assertEqual(
            results[0]["name"],
            "Full Availability Bank",
        )

        self.assertEqual(
            results[0]["availability_status"],
            "FULLY_AVAILABLE",
        )

        self.assertEqual(
            results[1]["name"],
            "Partial Availability Bank",
        )

        self.assertEqual(
            results[1]["availability_status"],
            "PARTIALLY_AVAILABLE",
        )

        self.assertEqual(
            results[2]["name"],
            "No Stock Bank",
        )

    def test_reserved_units_are_excluded(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.suggestions_url,
            {
                "radius_km": 10,
            },
        )

        results = response.data["results"]

        full_result = next(
            item
            for item in results
            if item["name"]
            == "Full Availability Bank"
        )

        partial_result = next(
            item
            for item in results
            if item["name"]
            == "Partial Availability Bank"
        )

        self.assertEqual(
            full_result["available_units"],
            4,
        )

        self.assertEqual(
            partial_result["available_units"],
            1,
        )

    def test_distant_bank_is_excluded(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.suggestions_url,
            {
                "radius_km": 10,
            },
        )

        names = [
            item["name"]
            for item in response.data["results"]
        ]

        self.assertNotIn(
            "Distant Availability Bank",
            names,
        )

    def test_unverified_bank_is_excluded(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.suggestions_url,
            {
                "radius_km": 10,
            },
        )

        names = [
            item["name"]
            for item in response.data["results"]
        ]

        self.assertNotIn(
            "Unverified Bank",
            names,
        )

    def test_invalid_radius_is_rejected(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.suggestions_url,
            {
                "radius_km": 500,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_missing_coordinates_are_rejected(
        self,
    ):
        request_without_coordinates = (
            create_blood_request(
                requester=self.requester,
                request_data={
                    "blood_bank": None,
                    "blood_group": self.blood_group,
                    "component": self.component,
                    "patient_name": "No Location Patient",
                    "units_required": 2,
                    "hospital_name": "Unknown Hospital",
                    "hospital_address": "Unknown",
                    "contact_phone": "9876543211",
                    "required_date": (
                        timezone.localdate()
                        + timedelta(days=1)
                    ),
                    "urgency": (
                        BloodRequest.Urgency.URGENT
                    ),
                },
            )
        )

        url = reverse(
            (
                "blood_requests:"
                "blood-request-suggested-banks"
            ),
            kwargs={
                "pk": (
                    request_without_coordinates.pk
                ),
            },
        )

        self.authenticate(self.requester)

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_other_user_cannot_view_suggestions(
        self,
    ):
        self.authenticate(self.other_user)

        response = self.client.get(
            self.suggestions_url
        )

        # The request is outside the user's queryset.
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_requester_can_assign_bank(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.post(
            self.assign_url,
            {
                "blood_bank": str(
                    self.full_bank.pk
                ),
                "reason": (
                    "Selected from nearby suggestions."
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.blood_bank,
            self.full_bank,
        )

        assignment = (
            BloodRequestBankAssignment.objects.get(
                blood_request=self.blood_request
            )
        )

        self.assertIsNone(
            assignment.previous_blood_bank
        )

        self.assertEqual(
            assignment.new_blood_bank,
            self.full_bank,
        )

        self.assertEqual(
            assignment.assigned_by,
            self.requester,
        )

    def test_same_bank_cannot_be_assigned_twice(
        self,
    ):
        self.authenticate(self.requester)

        payload = {
            "blood_bank": str(
                self.full_bank.pk
            ),
            "reason": "First assignment.",
        }

        first_response = self.client.post(
            self.assign_url,
            payload,
            format="json",
        )

        second_response = self.client.post(
            self.assign_url,
            payload,
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            BloodRequestBankAssignment.objects
            .filter(
                blood_request=self.blood_request
            )
            .count(),
            1,
        )

    def test_bank_cannot_change_after_review_begins(
        self,
    ):
        self.authenticate(self.requester)

        self.client.post(
            self.assign_url,
            {
                "blood_bank": str(
                    self.full_bank.pk
                ),
                "reason": "Initial assignment.",
            },
            format="json",
        )

        self.blood_request.refresh_from_db()

        transition_blood_request(
            blood_request=self.blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.admin,
            note="Review started.",
        )

        response = self.client.post(
            self.assign_url,
            {
                "blood_bank": str(
                    self.partial_bank.pk
                ),
                "reason": (
                    "Attempted late reassignment."
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.blood_bank,
            self.full_bank,
        )

    def test_unverified_bank_cannot_be_assigned(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.post(
            self.assign_url,
            {
                "blood_bank": str(
                    self.unverified_bank.pk
                ),
                "reason": "Invalid assignment.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.blood_request.refresh_from_db()

        self.assertIsNone(
            self.blood_request.blood_bank
        )

    def test_assignment_history_is_available(
        self,
    ):
        self.authenticate(self.requester)

        self.client.post(
            self.assign_url,
            {
                "blood_bank": str(
                    self.full_bank.pk
                ),
                "reason": "Nearby and fully available.",
            },
            format="json",
        )

        response = self.client.get(
            self.assignment_history_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0][
                "new_blood_bank_name"
            ],
            "Full Availability Bank",
        )

    def test_limit_is_applied(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.suggestions_url,
            {
                "radius_km": 10,
                "limit": 1,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["count"],
            1,
        )