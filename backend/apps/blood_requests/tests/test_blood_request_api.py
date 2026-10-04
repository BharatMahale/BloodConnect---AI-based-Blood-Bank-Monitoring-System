from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role, UserRole
from apps.blood_banks.models import BloodBank
from apps.blood_requests.models import (
    BloodRequest,
    BloodRequestStatusHistory,
)
from apps.blood_requests.services import (
    create_blood_request,
)
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
)
from apps.locations.models import Location


User = get_user_model()


class BloodRequestAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_inventory_reference",
            verbosity=0,
        )

        cls.requester = User.objects.create_user(
            email="requester-api@example.com",
            password="Requester@12345",
        )

        cls.bank_owner = User.objects.create_user(
            email="bank-api@example.com",
            password="BankOwner@12345",
        )

        cls.other_user = User.objects.create_user(
            email="other-api@example.com",
            password="Other@12345",
        )

        cls.admin = User.objects.create_user(
            email="admin-api@example.com",
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

        cls.application_admin = User.objects.create_user(
            email="application-role-admin@example.com",
            password="Admin@12345",
        )
        cls.staff_only = User.objects.create_user(
            email="request-staff-only@example.com",
            password="Staff@12345",
            is_staff=True,
        )
        admin_role, _ = Role.objects.get_or_create(
            code=Role.Code.ADMIN,
            defaults={"name": Role.Code.ADMIN.label},
        )
        UserRole.objects.create(
            user=cls.application_admin,
            role=admin_role,
            is_primary=True,
        )

        cls.location = Location.objects.create(
            address_line="Hospital Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude="21.349000",
            longitude="74.879000",
        )

        cls.blood_bank = BloodBank.objects.create(
            name="Phase 6B Test Blood Bank",
            location=cls.location,
            owner=cls.bank_owner,
            source=(
                BloodBank.Source.USER_REGISTERED
            ),
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            ),
            is_active=True,
            is_public=True,
        )

        cls.blood_group = BloodGroup.objects.get(
            name="O Positive"
        )

        cls.component = BloodComponent.objects.get(
            name="Whole Blood"
        )

        cls.blood_request = create_blood_request(
            requester=cls.requester,
            request_data={
                "blood_bank": cls.blood_bank,
                "blood_group": cls.blood_group,
                "component": cls.component,
                "patient_name": "Existing Patient",
                "units_required": 3,
                "hospital_name": "Test Hospital",
                "hospital_address": (
                    "Main Road, Shirpur"
                ),
                "contact_phone": "9876543210",
                "required_date": (
                    timezone.localdate()
                    + timedelta(days=1)
                ),
                "urgency": (
                    BloodRequest.Urgency.URGENT
                ),
                "additional_information": (
                    "Existing test request."
                ),
            },
        )

    def setUp(self):
        self.list_url = reverse(
            "blood_requests:blood-request-list"
        )

        self.detail_url = reverse(
            "blood_requests:blood-request-detail",
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

        self.update_status_url = reverse(
            (
                "blood_requests:"
                "blood-request-update-status"
            ),
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

        self.cancel_url = reverse(
            "blood_requests:blood-request-cancel",
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

        self.history_url = reverse(
            "blood_requests:blood-request-history",
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user
        )

    def get_create_payload(self):
        return {
            "blood_bank": str(
                self.blood_bank.pk
            ),
            "blood_group": str(
                self.blood_group.pk
            ),
            "component": str(
                self.component.pk
            ),
            "patient_name": "API Test Patient",
            "units_required": 2,
            "hospital_name": "Shirpur Hospital",
            "hospital_address": (
                "Main Road, Shirpur, Maharashtra"
            ),
            "contact_phone": "9876543211",
            "required_date": str(
                timezone.localdate()
                + timedelta(days=2)
            ),
            "urgency": (
                BloodRequest.Urgency.EMERGENCY
            ),
            "additional_information": (
                "Required urgently for surgery."
            ),
        }

    def test_anonymous_user_cannot_list_requests(
        self,
    ):
        response = self.client.get(
            self.list_url
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_authenticated_user_can_create_request(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.post(
            self.list_url,
            self.get_create_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertIn(
            "blood_request",
            response.data,
        )

        created_data = response.data[
            "blood_request"
        ]

        self.assertEqual(
            created_data["status"],
            BloodRequest.Status.PENDING,
        )

        self.assertEqual(
            created_data["units_required"],
            2,
        )

        created_request = (
            BloodRequest.objects.get(
                pk=created_data["id"]
            )
        )

        self.assertEqual(
            created_request.requester,
            self.requester,
        )

        self.assertEqual(
            created_request.status_history.count(),
            1,
        )

    def test_requester_can_list_own_requests(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.list_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["count"],
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            str(self.blood_request.pk),
        )

    def test_bank_owner_can_list_assigned_requests(
        self,
    ):
        self.authenticate(self.bank_owner)

        response = self.client.get(
            self.list_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["count"],
            1,
        )

    def test_unrelated_user_cannot_view_request(
        self,
    ):
        self.authenticate(self.other_user)

        response = self.client.get(
            self.detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_requester_cannot_update_status(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.UNDER_REVIEW
                ),
                "note": (
                    "Requester attempting update."
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.PENDING,
        )

    def test_bank_owner_retains_assigned_request_access(
        self,
    ):
        self.authenticate(self.bank_owner)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.UNDER_REVIEW
                ),
                "note": (
                    "Request verification started."
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
            self.blood_request.status,
            BloodRequest.Status.UNDER_REVIEW,
        )

        self.assertEqual(
            self.blood_request.reviewed_by,
            self.bank_owner,
        )

        self.assertEqual(
            self.blood_request.status_history.count(),
            2,
        )

    def test_invalid_direct_completion_is_rejected(
        self,
    ):
        self.authenticate(self.bank_owner)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.COMPLETED
                ),
                "note": "Invalid direct completion.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.PENDING,
        )

    def test_requester_can_cancel_own_request(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.post(
            self.cancel_url,
            {
                "reason": (
                    "Blood was arranged by the hospital."
                )
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.CANCELLED,
        )

        latest_history = (
            BloodRequestStatusHistory.objects
            .filter(
                blood_request=self.blood_request
            )
            .first()
        )

        self.assertEqual(
            latest_history.new_status,
            BloodRequest.Status.CANCELLED,
        )

    def test_other_user_cannot_cancel_request(
        self,
    ):
        self.authenticate(self.other_user)

        response = self.client.post(
            self.cancel_url,
            {
                "reason": "Unauthorized cancellation."
            },
            format="json",
        )

        # The request is outside the user's queryset,
        # so DRF safely returns 404.
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.PENDING,
        )

    def test_requester_can_view_history(
        self,
    ):
        self.authenticate(self.requester)

        response = self.client.get(
            self.history_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        results = response.data.get(
            "results",
            response.data,
        )

        self.assertEqual(
            len(results),
            1,
        )

        self.assertEqual(
            results[0]["new_status"],
            BloodRequest.Status.PENDING,
        )

    def test_admin_can_view_all_requests(
        self,
    ):
        self.authenticate(self.admin)

        response = self.client.get(
            self.list_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["count"],
            1,
        )

    def test_admin_can_update_request_status(
        self,
    ):
        self.authenticate(self.admin)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.UNDER_REVIEW
                ),
                "note": "Administrator review.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.UNDER_REVIEW,
        )

    def test_admin_role_without_is_staff_can_perform_global_request_operation(
        self,
    ):
        self.authenticate(self.application_admin)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.UNDER_REVIEW
                ),
                "note": "Application administrator review.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.blood_request.refresh_from_db()
        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.UNDER_REVIEW,
        )

    def test_is_staff_without_admin_role_cannot_perform_global_request_operation(
        self,
    ):
        self.authenticate(self.staff_only)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.UNDER_REVIEW
                ),
                "note": "Unauthorized staff review.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_past_required_date_is_rejected(
        self,
    ):
        self.authenticate(self.requester)

        payload = self.get_create_payload()

        payload["required_date"] = str(
            timezone.localdate()
            - timedelta(days=1)
        )

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "required_date",
            response.data,
        )
