import tempfile
from pathlib import Path
from django.core.management import call_command
from django.test import TestCase
from apps.blood_banks.models import BloodBank
from apps.locations.models import Location


class BloodBankImportCommandTests(TestCase):
    HEADERS = (
        "Sr No,Blood Bank Name,State,District,City,"
        "Address,Pincode,Contact No,Mobile,Helpline,"
        "Fax,Email,Website,Nodal Officer,"
        "Contact Nodal Officer,Mobile Nodal Officer,"
        "Email Nodal Officer,"
        "Qualification Nodal Officer,Category,"
        "Blood Component Available,Apheresis,"
        "Service Time,License #,"
        "Date License Obtained,Date of Renewal,"
        "Latitude,Longitude\n"
    )

    def create_dataset(self, content):
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            encoding="cp1252",
            newline="",
            delete=False,
        )

        temporary_file.write(self.HEADERS)
        temporary_file.write(content)
        temporary_file.close()

        self.addCleanup(
            lambda: Path(
                temporary_file.name
            ).unlink(missing_ok=True)
        )

        return temporary_file.name

    def test_import_creates_blood_bank(self):
        csv_path = self.create_dataset(
            "1,Test Blood Bank,Maharashtra,Dhule,"
            "Shirpur,Main Road,425405,02563234567,"
            "9876543210,,,bank@example.com,"
            "https://example.com,,,,,,Government,"
            "YES,NO,24X7,TEST-001,,,21.349,74.879\n"
        )

        call_command(
            "import_blood_banks",
            csv_path,
        )

        blood_bank = BloodBank.objects.get(
            source_record_id="1"
        )

        self.assertEqual(
            blood_bank.name,
            "Test Blood Bank",
        )
        self.assertEqual(
            blood_bank.category,
            BloodBank.Category.GOVERNMENT,
        )
        self.assertEqual(
            blood_bank.service_time,
            "24x7",
        )
        self.assertTrue(
            blood_bank.blood_component_available
        )
        self.assertFalse(
            blood_bank.apheresis_available
        )
        self.assertEqual(
            blood_bank.verification_status,
            BloodBank.VerificationStatus
            .DIRECTORY_IMPORTED,
        )

    def test_reimport_updates_instead_of_duplicating(self):
        csv_path = self.create_dataset(
            "1,Test Blood Bank,Maharashtra,Dhule,"
            "Shirpur,Main Road,425405,02563234567,"
            "9876543210,,,,,,,,,,Private,"
            "YES,NO,24X7,TEST-001,,,21.349,74.879\n"
        )

        call_command(
            "import_blood_banks",
            csv_path,
        )
        call_command(
            "import_blood_banks",
            csv_path,
        )

        self.assertEqual(
            BloodBank.objects.filter(
                source=BloodBank.Source.DIRECTORY_IMPORT
            ).count(),
            1,
        )

        self.assertEqual(
            Location.objects.count(),
            1,
        )

    def test_invalid_coordinates_become_null(self):
        csv_path = self.create_dataset(
            "2,Invalid Coordinate Bank,Maharashtra,"
            "Dhule,Shirpur,Main Road,425405,,,,,,,,"
            ",,,,Charity,NO,NO,24X7,TEST-002,,,0,0\n"
        )

        call_command(
            "import_blood_banks",
            csv_path,
        )

        blood_bank = BloodBank.objects.get(
            source_record_id="2"
        )

        self.assertIsNone(
            blood_bank.location.latitude
        )
        self.assertIsNone(
            blood_bank.location.longitude
        )

    def test_dry_run_saves_nothing(self):
        csv_path = self.create_dataset(
            "3,Dry Run Bank,Maharashtra,Dhule,"
            "Shirpur,Main Road,425405,,,,,,,,,,,,"
            "Government,YES,NO,24X7,TEST-003,,,"
            "21.349,74.879\n"
        )

        call_command(
            "import_blood_banks",
            csv_path,
            dry_run=True,
        )

        self.assertFalse(
            BloodBank.objects.filter(
                source_record_id="3"
            ).exists()
        )