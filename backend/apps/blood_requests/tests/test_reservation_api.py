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
    BloodRequestReservation,
)
from apps.blood_requests.services import (
    create_blood_request,
    transition_blood_request,
)
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)
from apps.locations.models import Location


User = get_user_model()


class ReservationAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_inventory_reference",
            verbosity=0,
        )

        cls.requester = User.objects.create_user(
            email="reservation-user@example.com",
            password="Requester@12345",
        )

        cls.bank_owner = User.objects.create_user(
            email="reservation-bank@example.com",
            password="BankOwner@12345",
        )

        cls.other_user = User.objects.create_user(
            email="reservation-other@example.com",
            password="Other@12345",
        )

        cls.location = Location.objects.create(
            address_line="Reservation Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude="21.349000",
            longitude="74.879000",
        )

        cls.blood_bank = BloodBank.objects.create(
            name="Reservation Test Blood Bank",
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

        cls.inventory = BloodInventory.objects.create(
            blood_bank=cls.blood_bank,
            blood_group=cls.blood_group,
            component=cls.component,
            total_units=10,
            reserved_units=0,
            last_updated_by=cls.bank_owner,
        )

    def setUp(self):
        self.blood_request = create_blood_request(
            requester=self.requester,
            request_data={
                "blood_bank": self.blood_bank,
                "blood_group": self.blood_group,
                "component": self.component,
                "patient_name": "Reservation Patient",
                "units_required": 4,
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
                    "Reservation integration test."
                ),
            },
        )

        self.reserve_url = reverse(
            (
                "blood_requests:"
                "blood-request-reserve-inventory"
            ),
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

        self.fulfil_url = reverse(
            (
                "blood_requests:"
                "blood-request-fulfil-inventory"
            ),
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

        self.release_url = reverse(
            (
                "blood_requests:"
                "blood-request-release-inventory"
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

        self.update_status_url = reverse(
            (
                "blood_requests:"
                "blood-request-update-status"
            ),
            kwargs={
                "pk": self.blood_request.pk,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user
        )

    def accept_request(self):
        transition_blood_request(
            blood_request=self.blood_request,
            new_status=(
                BloodRequest.Status.UNDER_REVIEW
            ),
            changed_by=self.bank_owner,
            note="Review started.",
        )

        self.blood_request = (
            transition_blood_request(
                blood_request=self.blood_request,
                new_status=(
                    BloodRequest.Status.ACCEPTED
                ),
                changed_by=self.bank_owner,
                note="Blood is available.",
            )
        )

    def reserve_units(self, quantity=4):
        self.authenticate(self.bank_owner)

        return self.client.post(
            self.reserve_url,
            {
                "quantity": quantity,
            },
            format="json",
        )

    def test_pending_request_cannot_reserve_stock(
        self,
    ):
        response = self.reserve_units(4)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.reserved_units,
            0,
        )

    def test_bank_owner_can_reserve_inventory(
        self,
    ):
        self.accept_request()

        response = self.reserve_units(4)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            10,
        )

        self.assertEqual(
            self.inventory.reserved_units,
            4,
        )

        reservation = (
            BloodRequestReservation.objects.get(
                blood_request=self.blood_request
            )
        )

        self.assertEqual(
            reservation.reserved_units,
            4,
        )

        self.assertEqual(
            reservation.fulfilled_units,
            0,
        )

    def test_direct_completed_status_cannot_bypass_fulfilment(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.COMPLETED
                ),
                "note": "Attempted direct completion.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.ACCEPTED,
        )
        self.assertEqual(
            self.blood_request.units_fulfilled,
            0,
        )
        self.assertEqual(self.inventory.total_units, 10)
        self.assertEqual(self.inventory.reserved_units, 4)
        self.assertFalse(
            InventoryTransaction.objects.filter(
                inventory=self.inventory,
                transaction_type=(
                    InventoryTransaction.Type.ISSUED
                ),
            ).exists()
        )

    def test_direct_partial_fulfilment_status_cannot_bypass_fulfilment(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status
                    .PARTIALLY_FULFILLED
                ),
                "units_fulfilled": 2,
                "note": "Attempted direct partial fulfilment.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.ACCEPTED,
        )
        self.assertEqual(
            self.blood_request.units_fulfilled,
            0,
        )
        self.assertEqual(self.inventory.total_units, 10)
        self.assertEqual(self.inventory.reserved_units, 4)
        self.assertFalse(
            InventoryTransaction.objects.filter(
                inventory=self.inventory,
                transaction_type=(
                    InventoryTransaction.Type.ISSUED
                ),
            ).exists()
        )

    def test_requester_cannot_reserve_inventory(
        self,
    ):
        self.accept_request()
        self.authenticate(self.requester)

        response = self.client.post(
            self.reserve_url,
            {"quantity": 4},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_over_reservation_is_rejected(self):
        self.accept_request()

        response = self.reserve_units(11)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.reserved_units,
            0,
        )

    def test_partial_fulfilment_updates_everything(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        response = self.client.post(
            self.fulfil_url,
            {
                "quantity": 2,
                "note": "Two units supplied.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        reservation = (
            BloodRequestReservation.objects.get(
                blood_request=self.blood_request
            )
        )

        self.assertEqual(
            self.inventory.total_units,
            8,
        )

        self.assertEqual(
            self.inventory.reserved_units,
            2,
        )

        self.assertEqual(
            reservation.reserved_units,
            2,
        )

        self.assertEqual(
            reservation.fulfilled_units,
            2,
        )

        self.assertEqual(
            self.blood_request.units_fulfilled,
            2,
        )

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status
            .PARTIALLY_FULFILLED,
        )

    def test_multiple_partial_fulfilments_work(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        first_response = self.client.post(
            self.fulfil_url,
            {
                "quantity": 1,
                "note": "First unit supplied.",
            },
            format="json",
        )

        second_response = self.client.post(
            self.fulfil_url,
            {
                "quantity": 1,
                "note": "Second unit supplied.",
            },
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            8,
        )

        self.assertEqual(
            self.inventory.reserved_units,
            2,
        )

        self.assertEqual(
            self.blood_request.units_fulfilled,
            2,
        )

    def test_complete_fulfilment_closes_request(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        response = self.client.post(
            self.fulfil_url,
            {
                "quantity": 4,
                "note": "All units supplied.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        reservation = (
            BloodRequestReservation.objects.get(
                blood_request=self.blood_request
            )
        )

        self.assertEqual(
            self.inventory.total_units,
            6,
        )

        self.assertEqual(
            self.inventory.reserved_units,
            0,
        )

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.COMPLETED,
        )

        self.assertEqual(
            self.blood_request.units_fulfilled,
            4,
        )

        self.assertEqual(
            reservation.status,
            BloodRequestReservation
            .Status.FULFILLED,
        )

        transaction_record = (
            InventoryTransaction.objects.get(
                reference_number=(
                    self.blood_request.request_number
                )
            )
        )

        self.assertEqual(
            transaction_record.quantity_change,
            -4,
        )

    def test_failed_fulfilment_rolls_back_changes(
        self,
    ):
        self.accept_request()
        self.reserve_units(2)

        response = self.client.post(
            self.fulfil_url,
            {
                "quantity": 3,
                "note": "Invalid fulfilment.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        reservation = (
            BloodRequestReservation.objects.get(
                blood_request=self.blood_request
            )
        )

        self.assertEqual(
            self.inventory.total_units,
            10,
        )

        self.assertEqual(
            self.inventory.reserved_units,
            2,
        )

        self.assertEqual(
            reservation.reserved_units,
            2,
        )

        self.assertEqual(
            self.blood_request.units_fulfilled,
            0,
        )

        self.assertFalse(
            InventoryTransaction.objects.filter(
                reference_number=(
                    self.blood_request.request_number
                )
            ).exists()
        )

    def test_manual_release_restores_availability(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        response = self.client.post(
            self.release_url,
            {
                "reason": (
                    "Request reassigned to another bank."
                )
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()

        reservation = (
            BloodRequestReservation.objects.get(
                blood_request=self.blood_request
            )
        )

        self.assertEqual(
            self.inventory.total_units,
            10,
        )

        self.assertEqual(
            self.inventory.reserved_units,
            0,
        )

        self.assertEqual(
            reservation.reserved_units,
            0,
        )

        self.assertEqual(
            reservation.status,
            BloodRequestReservation.Status.RELEASED,
        )

    def test_cancellation_releases_reserved_units(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        self.authenticate(self.requester)

        response = self.client.post(
            self.cancel_url,
            {
                "reason": (
                    "Blood arranged by the hospital."
                )
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        reservation = (
            BloodRequestReservation.objects.get(
                blood_request=self.blood_request
            )
        )

        self.assertEqual(
            self.inventory.reserved_units,
            0,
        )

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.CANCELLED,
        )

        self.assertEqual(
            reservation.status,
            BloodRequestReservation.Status.RELEASED,
        )

    def test_expiry_releases_reserved_units(
        self,
    ):
        self.accept_request()
        self.reserve_units(4)

        response = self.client.post(
            self.update_status_url,
            {
                "new_status": (
                    BloodRequest.Status.EXPIRED
                ),
                "note": "Request validity expired.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()
        self.blood_request.refresh_from_db()

        self.assertEqual(
            self.inventory.reserved_units,
            0,
        )

        self.assertEqual(
            self.blood_request.status,
            BloodRequest.Status.EXPIRED,
        )
