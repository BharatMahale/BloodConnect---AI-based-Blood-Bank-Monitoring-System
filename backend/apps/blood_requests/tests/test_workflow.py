from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from apps.blood_banks.models import BloodBank
from apps.blood_requests.models import (
    BloodRequest,
    BloodRequestStatusHistory,
)
from apps.blood_requests.services import (
    create_blood_request,
    transition_blood_request,
)
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
)
from apps.locations.models import Location


User = get_user_model()


class BloodRequestWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_inventory_reference",
            verbosity=0,
        )

        cls.requester = User.objects.create_user(
            email="requester@example.com",
            password="Requester@12345",
        )

        cls.bank_staff = User.objects.create_user(
            email="staff@example.com",
            password="Staff@12345",
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
            name="Workflow Test Blood Bank",
            location=cls.location,
            owner=cls.bank_staff,
            source=BloodBank.Source.USER_REGISTERED,
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

    def create_request(self):
        return create_blood_request(
            requester=self.requester,
            request_data={
                "blood_bank": self.blood_bank,
                "blood_group": self.blood_group,
                "component": self.component,
                "patient_name": "Test Patient",
                "units_required": 4,
                "hospital_name": "Test Hospital",
                "hospital_address": (
                    "Shirpur, Maharashtra"
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
                    "Required for surgery."
                ),
            },
        )

    def test_service_creates_pending_request(self):
        blood_request = self.create_request()

        self.assertEqual(
            blood_request.status,
            BloodRequest.Status.PENDING,
        )

        self.assertEqual(
            blood_request.units_fulfilled,
            0,
        )

        history = (
            BloodRequestStatusHistory.objects.get(
                blood_request=blood_request
            )
        )

        self.assertEqual(
            history.previous_status,
            "",
        )

        self.assertEqual(
            history.new_status,
            BloodRequest.Status.PENDING,
        )

        self.assertEqual(
            history.changed_by,
            self.requester,
        )

    def test_pending_can_move_to_under_review(
        self,
    ):
        blood_request = self.create_request()

        updated_request = transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.bank_staff,
            note="Request verification started.",
        )

        self.assertEqual(
            updated_request.status,
            BloodRequest.Status.UNDER_REVIEW,
        )

        self.assertEqual(
            updated_request.reviewed_by,
            self.bank_staff,
        )

    def test_pending_cannot_move_directly_to_completed(
        self,
    ):
        blood_request = self.create_request()

        with self.assertRaises(ValidationError):
            transition_blood_request(
                blood_request=blood_request,
                new_status=(
                    BloodRequest.Status.COMPLETED
                ),
                changed_by=self.bank_staff,
                note="Invalid direct completion.",
            )

        blood_request.refresh_from_db()

        self.assertEqual(
            blood_request.status,
            BloodRequest.Status.PENDING,
        )

    def test_request_can_be_accepted(self):
        blood_request = self.create_request()

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.bank_staff,
            note="Checking availability.",
        )

        accepted_request = transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.ACCEPTED
            ),
            changed_by=self.bank_staff,
            note="Required blood is available.",
        )

        self.assertEqual(
            accepted_request.status,
            BloodRequest.Status.ACCEPTED,
        )

    def test_partial_fulfilment_updates_units(self):
        blood_request = self.create_request()

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.bank_staff,
        )

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.ACCEPTED
            ),
            changed_by=self.bank_staff,
        )

        updated_request = transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status
                .PARTIALLY_FULFILLED
            ),
            changed_by=self.bank_staff,
            units_fulfilled=2,
            note="Two units supplied.",
        )

        self.assertEqual(
            updated_request.units_fulfilled,
            2,
        )

        self.assertEqual(
            updated_request.remaining_units,
            2,
        )

    def test_completion_fulfils_all_units(self):
        blood_request = self.create_request()

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.bank_staff,
        )

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.ACCEPTED
            ),
            changed_by=self.bank_staff,
        )

        completed_request = transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.COMPLETED
            ),
            changed_by=self.bank_staff,
            note="All units supplied.",
        )

        self.assertEqual(
            completed_request.status,
            BloodRequest.Status.COMPLETED,
        )

        self.assertEqual(
            completed_request.units_fulfilled,
            completed_request.units_required,
        )

    def test_rejection_requires_reason(self):
        blood_request = self.create_request()

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.bank_staff,
        )

        with self.assertRaises(ValidationError):
            transition_blood_request(
                blood_request=blood_request,
                new_status=(
                    BloodRequest.Status.REJECTED
                ),
                changed_by=self.bank_staff,
                note="",
            )

    def test_terminal_request_cannot_change_status(
        self,
    ):
        blood_request = self.create_request()

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.CANCELLED
            ),
            changed_by=self.requester,
            note="Blood is no longer required.",
        )

        with self.assertRaises(ValidationError):
            transition_blood_request(
                blood_request=blood_request,
                new_status=(
                    BloodRequest.Status.UNDER_REVIEW
                ),
                changed_by=self.bank_staff,
                note="Trying to reopen request.",
            )

    def test_every_transition_creates_history(
        self,
    ):
        blood_request = self.create_request()

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.bank_staff,
            note="Review started.",
        )

        transition_blood_request(
            blood_request=blood_request,
            new_status=(
                BloodRequest.Status.ACCEPTED
            ),
            changed_by=self.bank_staff,
            note="Blood available.",
        )

        history = (
            BloodRequestStatusHistory.objects
            .filter(
                blood_request=blood_request
            )
            .order_by("created_at")
        )

        self.assertEqual(
            history.count(),
            3,
        )

        self.assertEqual(
            history[0].new_status,
            BloodRequest.Status.PENDING,
        )

        self.assertEqual(
            history[1].new_status,
            BloodRequest.Status.UNDER_REVIEW,
        )

        self.assertEqual(
            history[2].new_status,
            BloodRequest.Status.ACCEPTED,
        )