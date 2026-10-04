from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.blood_banks.models import BloodBank
from apps.donors.models import (
    DonationRecord,
    DonorProfile,
)
from apps.donors.services.donations import (
    record_donation,
)
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)
from apps.locations.models import Location


User = get_user_model()


class DonationInventoryIntegrationTests(TestCase):
    def setUp(self):
        self.bank_owner = User.objects.create_user(
            email="bank-owner@example.com",
            password="BankOwner@12345",
        )

        self.donor_user = User.objects.create_user(
            email="donor-inventory@example.com",
            password="Donor@12345",
        )

        self.location = Location.objects.create(
            address_line="Main Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude=Decimal("21.349500"),
            longitude=Decimal("74.880200"),
        )

        self.blood_bank = BloodBank.objects.create(
            owner=self.bank_owner,
            location=self.location,
            name="Integration Test Blood Bank",
            category=BloodBank.Category.GOVERNMENT,
            source=BloodBank.Source.USER_REGISTERED,
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            ),
            is_active=True,
            is_public=True,
        )

        self.blood_group, _ = (
            BloodGroup.objects.get_or_create(
                name="O Positive",
            )
        )

        self.whole_blood, _ = (
            BloodComponent.objects.get_or_create(
                name="Whole Blood",
            )
        )

        self.donor = DonorProfile.objects.create(
            user=self.donor_user,
            blood_group=self.blood_group,
            date_of_birth=date(2002, 5, 20),
            gender=DonorProfile.Gender.MALE,
            weight_kg=Decimal("65.00"),
            phone="9876543210",
            address="Shirpur",
            city="Shirpur",
            state="Maharashtra",
            pincode="425405",
            latitude=Decimal("21.349500"),
            longitude=Decimal("74.880200"),
            is_available=True,
            medical_declaration_accepted=True,
        )

    def test_completed_donation_adds_inventory(self):
        donation = record_donation(
            donor=self.donor,
            blood_bank=self.blood_bank,
            donation_date=date.today(),
            units_donated=1,
            status=DonationRecord.Status.COMPLETED,
            notes="Successful donation",
            recorded_by=self.bank_owner,
        )

        inventory = BloodInventory.objects.get(
            blood_bank=self.blood_bank,
            blood_group=self.blood_group,
            component=self.whole_blood,
        )

        self.assertEqual(
            inventory.total_units,
            1,
        )
        self.assertEqual(
            inventory.reserved_units,
            0,
        )

        transaction = InventoryTransaction.objects.get(
            inventory=inventory,
        )

        self.assertEqual(
            transaction.transaction_type,
            InventoryTransaction.Type.DONATION,
        )
        self.assertEqual(
            transaction.quantity_change,
            1,
        )
        self.assertEqual(
            transaction.quantity_before,
            0,
        )
        self.assertEqual(
            transaction.quantity_after,
            1,
        )
        self.assertEqual(
            transaction.reference_number,
            f"DONATION-{donation.id}",
        )

    def test_completed_donation_updates_donor(self):
        record_donation(
            donor=self.donor,
            blood_bank=self.blood_bank,
            donation_date=date.today(),
            units_donated=1,
            status=DonationRecord.Status.COMPLETED,
            notes="Successful donation",
            recorded_by=self.bank_owner,
        )

        self.donor.refresh_from_db()

        self.assertEqual(
            self.donor.last_donation_date,
            date.today(),
        )
        self.assertFalse(
            self.donor.is_available
        )

    def test_second_donation_increases_existing_inventory(self):
        inventory = BloodInventory.objects.create(
            blood_bank=self.blood_bank,
            blood_group=self.blood_group,
            component=self.whole_blood,
            total_units=5,
            reserved_units=1,
            last_updated_by=self.bank_owner,
        )

        record_donation(
            donor=self.donor,
            blood_bank=self.blood_bank,
            donation_date=date.today(),
            units_donated=2,
            status=DonationRecord.Status.COMPLETED,
            notes="Two units received",
            recorded_by=self.bank_owner,
        )

        inventory.refresh_from_db()

        self.assertEqual(
            inventory.total_units,
            7,
        )
        self.assertEqual(
            inventory.reserved_units,
            1,
        )

    def test_cancelled_donation_does_not_change_inventory(self):
        record_donation(
            donor=self.donor,
            blood_bank=self.blood_bank,
            donation_date=date.today(),
            units_donated=1,
            status=DonationRecord.Status.CANCELLED,
            notes="Donor cancelled",
            recorded_by=self.bank_owner,
        )

        self.assertFalse(
            BloodInventory.objects.filter(
                blood_bank=self.blood_bank,
                blood_group=self.blood_group,
                component=self.whole_blood,
            ).exists()
        )

        self.donor.refresh_from_db()

        self.assertTrue(
            self.donor.is_available
        )
        self.assertIsNone(
            self.donor.last_donation_date
        )

    def test_rejected_donation_does_not_change_inventory(self):
        record_donation(
            donor=self.donor,
            blood_bank=self.blood_bank,
            donation_date=date.today(),
            units_donated=1,
            status=DonationRecord.Status.REJECTED,
            notes="Donation rejected",
            recorded_by=self.bank_owner,
        )

        self.assertEqual(
            BloodInventory.objects.count(),
            0,
        )
        self.assertEqual(
            InventoryTransaction.objects.count(),
            0,
        )