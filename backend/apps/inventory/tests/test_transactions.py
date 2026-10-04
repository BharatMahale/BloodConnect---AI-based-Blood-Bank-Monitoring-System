from django.core.exceptions import ValidationError
from django.test import TestCase
from apps.accounts.models import User
from apps.blood_banks.models import BloodBank
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)
from apps.inventory.services.transactions import (
    adjust_inventory,
    record_inventory_transaction,
)
from apps.locations.models import Location


class InventoryTransactionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="staff@example.com",
            password="StrongPass@123",
        )

        self.location = Location.objects.create(
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
        )

        self.blood_bank = BloodBank.objects.create(
            name="Test Blood Bank",
            location=self.location,
            owner=self.user,
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            ),
        )

        self.blood_group = BloodGroup.objects.create(
            code="O+",
            name="O Positive",
        )

        self.component = BloodComponent.objects.create(
            code="PRBC",
            name="Packed Red Blood Cells",
        )

        self.inventory = BloodInventory.objects.create(
            blood_bank=self.blood_bank,
            blood_group=self.blood_group,
            component=self.component,
            total_units=0,
            reserved_units=0,
            minimum_threshold=5,
        )

    def test_donation_adds_units(self):
        inventory_transaction = (
            record_inventory_transaction(
                inventory=self.inventory,
                transaction_type=(
                    InventoryTransaction.Type.DONATION
                ),
                quantity=10,
                reason="Donation collection",
                created_by=self.user,
            )
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            10,
        )
        self.assertEqual(
            inventory_transaction.quantity_before,
            0,
        )
        self.assertEqual(
            inventory_transaction.quantity_after,
            10,
        )
        self.assertEqual(
            inventory_transaction.quantity_change,
            10,
        )

    def test_issuing_units_reduces_stock(self):
        self.inventory.total_units = 10
        self.inventory.save()

        record_inventory_transaction(
            inventory=self.inventory,
            transaction_type=(
                InventoryTransaction.Type.ISSUED
            ),
            quantity=3,
            reason="Issued to hospital",
            created_by=self.user,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            7,
        )

    def test_stock_cannot_become_negative(self):
        self.inventory.total_units = 2
        self.inventory.save()

        with self.assertRaises(ValidationError):
            record_inventory_transaction(
                inventory=self.inventory,
                transaction_type=(
                    InventoryTransaction.Type.ISSUED
                ),
                quantity=5,
                reason="Invalid issue attempt",
                created_by=self.user,
            )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            2,
        )
        self.assertEqual(
            InventoryTransaction.objects.count(),
            0,
        )

    def test_stock_cannot_drop_below_reserved_units(self):
        self.inventory.total_units = 10
        self.inventory.reserved_units = 8
        self.inventory.save()

        with self.assertRaises(ValidationError):
            record_inventory_transaction(
                inventory=self.inventory,
                transaction_type=(
                    InventoryTransaction.Type.ISSUED
                ),
                quantity=5,
                reason="Invalid issue",
                created_by=self.user,
            )

    def test_adjustment_creates_audit_record(self):
        self.inventory.total_units = 10
        self.inventory.save()

        inventory_transaction = adjust_inventory(
            inventory=self.inventory,
            new_total_units=8,
            reason="Physical stock recount",
            created_by=self.user,
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.total_units,
            8,
        )
        self.assertEqual(
            inventory_transaction.quantity_change,
            -2,
        )
        self.assertEqual(
            inventory_transaction.transaction_type,
            InventoryTransaction.Type.ADJUSTMENT,
        )

    def test_zero_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            record_inventory_transaction(
                inventory=self.inventory,
                transaction_type=(
                    InventoryTransaction.Type.DONATION
                ),
                quantity=0,
                reason="Invalid transaction",
                created_by=self.user,
            )

    def test_reason_is_required(self):
        with self.assertRaises(ValidationError):
            record_inventory_transaction(
                inventory=self.inventory,
                transaction_type=(
                    InventoryTransaction.Type.DONATION
                ),
                quantity=5,
                reason="",
                created_by=self.user,
            )