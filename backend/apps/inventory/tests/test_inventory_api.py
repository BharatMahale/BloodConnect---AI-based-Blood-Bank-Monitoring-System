from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role, UserRole
from apps.blood_banks.models import BloodBank
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)
from apps.locations.models import Location


User = get_user_model()


class BloodInventoryAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_inventory_reference",
            verbosity=0,
        )

        cls.owner = User.objects.create_user(
            email="owner@example.com",
            password="Owner@12345",
        )

        cls.other_user = User.objects.create_user(
            email="other@example.com",
            password="Other@12345",
        )

        cls.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="Admin@12345",
        )

        cls.application_admin = User.objects.create_user(
            email="application-admin@example.com",
            password="Admin@12345",
        )
        cls.staff_only = User.objects.create_user(
            email="staff-only@example.com",
            password="Staff@12345",
            is_staff=True,
        )
        cls.blood_bank_staff = User.objects.create_user(
            email="role-staff@example.com",
            password="RoleStaff@12345",
        )
        admin_role, _ = Role.objects.get_or_create(
            code=Role.Code.ADMIN,
            defaults={"name": Role.Code.ADMIN.label},
        )
        bank_staff_role, _ = Role.objects.get_or_create(
            code=Role.Code.BLOOD_BANK_STAFF,
            defaults={"name": Role.Code.BLOOD_BANK_STAFF.label},
        )
        UserRole.objects.create(
            user=cls.application_admin,
            role=admin_role,
            is_primary=True,
        )
        UserRole.objects.create(
            user=cls.blood_bank_staff,
            role=bank_staff_role,
            is_primary=True,
        )

        cls.location = Location.objects.create(
            address_line="Main Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude="21.349000",
            longitude="74.879000",
        )

        cls.blood_bank = BloodBank.objects.create(
            name="Phase 5B Test Blood Bank",
            location=cls.location,
            owner=cls.owner,
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
            total_units=0,
            reserved_units=0,
        )

    def setUp(self):
        self.list_url = reverse(
            "inventory:blood-inventory-list"
        )

        self.detail_url = reverse(
            "inventory:blood-inventory-detail",
            kwargs={
                "pk": self.inventory.pk,
            },
        )

        self.update_url = reverse(
            "inventory:blood-inventory-update-stock",
            kwargs={
                "pk": self.inventory.pk,
            },
        )

        self.transactions_url = reverse(
            "inventory:blood-inventory-transactions",
            kwargs={
                "pk": self.inventory.pk,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user
        )

    def clear_authentication(self):
        self.client.force_authenticate(
            user=None
        )

    def add_public_inventories(self, count, offset):
        for index in range(count):
            blood_bank = BloodBank.objects.create(
                name=f"Query Bank {offset + index}",
                location=self.location,
                owner=self.other_user,
                source=BloodBank.Source.USER_REGISTERED,
                verification_status=(
                    BloodBank.VerificationStatus.VERIFIED
                ),
                is_active=True,
                is_public=True,
            )
            BloodInventory.objects.create(
                blood_bank=blood_bank,
                blood_group=self.blood_group,
                component=self.component,
                total_units=10,
                reserved_units=2,
            )

    def test_authenticated_inventory_query_scaling(self):
        self.authenticate(self.owner)
        measurements = []

        for expected_count, additional_count in (
            (1, 0),
            (10, 9),
            (20, 10),
        ):
            self.add_public_inventories(
                additional_count,
                expected_count - additional_count,
            )
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(self.list_url)
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

        one_item_queries = measurements[0][1]
        twenty_item_queries = measurements[-1][1]
        self.assertLessEqual(
            twenty_item_queries,
            one_item_queries + 1,
            measurements,
        )

    def test_public_user_can_list_inventory(self):
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

    def test_public_user_can_view_inventory_detail(
        self,
    ):
        response = self.client.get(
            self.detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["total_units"],
            0,
        )

        self.assertEqual(
            response.data["available_units"],
            0,
        )

        self.assertNotIn(
            "reserved_units",
            response.data,
        )

    def test_public_inventory_excludes_private_bank_and_transactions(self):
        private_bank = BloodBank.objects.create(
            name="Private Inventory Bank",
            location=self.location,
            owner=self.other_user,
            source=BloodBank.Source.USER_REGISTERED,
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            ),
            is_active=True,
            is_public=False,
        )
        private_inventory = BloodInventory.objects.create(
            blood_bank=private_bank,
            blood_group=self.blood_group,
            component=self.component,
            total_units=12,
            reserved_units=5,
        )
        InventoryTransaction.objects.create(
            inventory=self.inventory,
            transaction_type=InventoryTransaction.Type.DONATION,
            quantity_change=3,
            quantity_before=0,
            quantity_after=3,
            reason="Internal test transaction",
            created_by=self.owner,
        )

        list_response = self.client.get(self.list_url)
        private_response = self.client.get(
            reverse(
                "inventory:blood-inventory-detail",
                kwargs={"pk": private_inventory.pk},
            )
        )
        transactions_response = self.client.get(
            self.transactions_url,
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            str(private_inventory.pk),
            str(list_response.data),
        )
        self.assertEqual(private_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(
            transactions_response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_anonymous_user_cannot_update_stock(
        self,
    ):
        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.DONATION
                ),
                "quantity": 10,
                "reason": "Test donation",
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            0,
        )

    def test_bank_owner_retains_own_bank_inventory_access(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.DONATION
                ),
                "quantity": 10,
                "reason": (
                    "Collected during donation camp"
                ),
                "reference_number": "CAMP-001",
            },
            format="json",
        )

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
            response.data["available_units"],
            10,
        )

        transaction = (
            InventoryTransaction.objects.get(
                inventory=self.inventory
            )
        )

        self.assertEqual(
            transaction.quantity_before,
            0,
        )

        self.assertEqual(
            transaction.quantity_change,
            10,
        )

        self.assertEqual(
            transaction.quantity_after,
            10,
        )

        self.assertEqual(
            transaction.created_by,
            self.owner,
        )

    def test_owner_can_issue_available_stock(self):
        self.inventory.total_units = 10
        self.inventory.save(
            update_fields=["total_units"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.ISSUED
                ),
                "quantity": 3,
                "reason": (
                    "Issued for approved request"
                ),
                "reference_number": "REQ-001",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            7,
        )

    def test_stock_cannot_become_negative(self):
        self.inventory.total_units = 5
        self.inventory.save(
            update_fields=["total_units"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.ISSUED
                ),
                "quantity": 10,
                "reason": (
                    "Negative inventory test"
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            5,
        )

        self.assertEqual(
            InventoryTransaction.objects.filter(
                inventory=self.inventory
            ).count(),
            0,
        )

    def test_inventory_cannot_fall_below_reserved(
        self,
    ):
        self.inventory.total_units = 10
        self.inventory.reserved_units = 6
        self.inventory.save(
            update_fields=[
                "total_units",
                "reserved_units",
            ]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.ISSUED
                ),
                "quantity": 5,
                "reason": (
                    "Reserved inventory protection test"
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            10,
        )

    def test_owner_can_adjust_inventory(self):
        self.inventory.total_units = 10
        self.inventory.save(
            update_fields=["total_units"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.ADJUSTMENT
                ),
                "quantity": 15,
                "reason": (
                    "Physical inventory verification"
                ),
                "reference_number": "AUDIT-001",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            15,
        )

        transaction = (
            InventoryTransaction.objects.get(
                inventory=self.inventory
            )
        )

        self.assertEqual(
            transaction.transaction_type,
            InventoryTransaction.Type.ADJUSTMENT,
        )

        self.assertEqual(
            transaction.quantity_change,
            5,
        )

    def test_adjustment_can_set_inventory_to_zero(
        self,
    ):
        self.inventory.total_units = 5
        self.inventory.reserved_units = 0
        self.inventory.save(
            update_fields=[
                "total_units",
                "reserved_units",
            ]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.ADJUSTMENT
                ),
                "quantity": 0,
                "reason": (
                    "Physical count found no stock"
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            0,
        )

    def test_bank_owner_cannot_manage_other_bank_inventory(
        self,
    ):
        self.authenticate(self.other_user)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.DONATION
                ),
                "quantity": 10,
                "reason": "Unauthorized update",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            0,
        )

    def test_admin_can_update_inventory(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.RECEIVED
                ),
                "quantity": 8,
                "reason": (
                    "Received from another facility"
                ),
                "reference_number": "RCV-001",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            8,
        )

    def test_admin_role_without_is_staff_can_perform_global_inventory_operation(
        self,
    ):
        self.authenticate(self.application_admin)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.RECEIVED
                ),
                "quantity": 8,
                "reason": "Application admin receipt",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.total_units, 8)

    def test_is_staff_without_admin_role_cannot_manage_other_bank_inventory(
        self,
    ):
        self.authenticate(self.staff_only)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.RECEIVED
                ),
                "quantity": 8,
                "reason": "Unauthorized staff receipt",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_blood_bank_staff_role_has_no_implicit_global_access(self):
        self.authenticate(self.blood_bank_staff)

        response = self.client.post(
            self.update_url,
            {
                "transaction_type": (
                    InventoryTransaction.Type.RECEIVED
                ),
                "quantity": 8,
                "reason": "Role-only staff receipt",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_view_transaction_history(
        self,
    ):
        InventoryTransaction.objects.create(
            inventory=self.inventory,
            transaction_type=(
                InventoryTransaction.Type.DONATION
            ),
            quantity_change=5,
            quantity_before=0,
            quantity_after=5,
            reason="Test history",
            reference_number="HISTORY-001",
            created_by=self.owner,
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.transactions_url
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
            results[0]["quantity_change"],
            5,
        )

    def test_other_user_cannot_view_history(
        self,
    ):
        self.authenticate(self.other_user)

        response = self.client.get(
            self.transactions_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
