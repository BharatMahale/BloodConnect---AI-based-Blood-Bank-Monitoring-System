from django.test import TestCase
from apps.blood_banks.models import BloodBank
from apps.locations.models import Location


class BloodBankModelTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(
            address_line="Test Hospital Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude="21.349000",
            longitude="74.879000",
        )

    def test_blood_bank_can_be_created(self):
        blood_bank = BloodBank.objects.create(
            name="Test Blood Bank",
            location=self.location,
            category=BloodBank.Category.GOVERNMENT,
            source=BloodBank.Source.ADMIN_CREATED,
        )

        self.assertEqual(
            str(blood_bank),
            "Test Blood Bank",
        )
        self.assertEqual(
            blood_bank.slug,
            "test-blood-bank",
        )
        self.assertFalse(blood_bank.is_verified)

    def test_duplicate_names_receive_unique_slugs(self):
        first_bank = BloodBank.objects.create(
            name="City Blood Bank",
            location=self.location,
        )

        second_location = Location.objects.create(
            city="Dhule",
            district="Dhule",
            state="Maharashtra",
        )

        second_bank = BloodBank.objects.create(
            name="City Blood Bank",
            location=second_location,
        )

        self.assertNotEqual(
            first_bank.slug,
            second_bank.slug,
        )

    def test_imported_bank_is_not_verified(self):
        blood_bank = BloodBank.objects.create(
            name="Imported Blood Bank",
            location=self.location,
            source=BloodBank.Source.DIRECTORY_IMPORT,
            source_record_id="1",
            verification_status=(
                BloodBank.VerificationStatus.DIRECTORY_IMPORTED
            ),
        )

        self.assertFalse(blood_bank.is_verified)
        self.assertEqual(
            blood_bank.data_source_label,
            "Imported directory information",
        )