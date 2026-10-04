import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from django.core.exceptions import ValidationError
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.core.validators import (
    EmailValidator,
    URLValidator,
)
from django.db import transaction
from apps.blood_banks.models import BloodBank
from apps.locations.models import Location


class Command(BaseCommand):
    help = (
        "Import blood-bank directory records from the "
        "Blood Bank Directory - India CSV file."
    )

    NULL_VALUES = {
        "",
        "na",
        "n/a",
        "none",
        "null",
        "nan",
        "-",
        "--",
    }

    TRUE_VALUES = {
        "yes",
        "y",
        "true",
        "1",
    }

    FALSE_VALUES = {
        "no",
        "n",
        "false",
        "0",
    }

    CATEGORY_MAPPING = {
        "government": BloodBank.Category.GOVERNMENT,
        "private": BloodBank.Category.PRIVATE,
        "charity": BloodBank.Category.CHARITY,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="Path to the blood-bank CSV file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Validate and process the CSV without "
                "saving database changes."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Import only the first specified records.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).resolve()
        dry_run = options["dry_run"]
        limit = options["limit"]

        self._validate_file(csv_path)

        statistics = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "invalid_coordinates": 0,
            "invalid_emails": 0,
            "invalid_websites": 0,
            "errors": 0,
        }

        self.stdout.write(
            self.style.NOTICE(
                f"Reading dataset: {csv_path}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run enabled: no database changes "
                    "will be saved."
                )
            )

        try:
            with csv_path.open(
                mode="r",
                encoding="cp1252",
                newline="",
            ) as csv_file:
                reader = csv.DictReader(csv_file)

                if not reader.fieldnames:
                    raise CommandError(
                        "The CSV file has no header row."
                    )

                reader.fieldnames = [
                    self.clean_column_name(column)
                    for column in reader.fieldnames
                ]

                self._validate_headers(reader.fieldnames)

                with transaction.atomic():
                    for row_number, raw_row in enumerate(
                        reader,
                        start=2,
                    ):
                        if (
                            limit is not None
                            and statistics["processed"] >= limit
                        ):
                            break

                        statistics["processed"] += 1

                        cleaned_row = {
                            self.clean_column_name(key): value
                            for key, value in raw_row.items()
                        }

                        try:
                            with transaction.atomic():
                                result = self.import_row(
                                    cleaned_row,
                                    statistics,
                                )

                            statistics[result] += 1

                        except Exception as error:
                            statistics["errors"] += 1
                            statistics["skipped"] += 1

                            self.stderr.write(
                                self.style.ERROR(
                                    f"Row {row_number} skipped: "
                                    f"{error}"
                                )
                            )

                    if dry_run:
                        transaction.set_rollback(True)

        except UnicodeDecodeError as error:
            raise CommandError(
                "The dataset could not be read using "
                "Windows-1252 encoding."
            ) from error

        self.print_summary(
            statistics=statistics,
            dry_run=dry_run,
        )

    def import_row(self, row, statistics):
        source_record_id = self.clean_text(
            row.get("Sr No")
        )
        name = self.clean_text(
            row.get("Blood Bank Name")
        )

        if not source_record_id:
            raise ValueError(
                "Source row number is missing."
            )

        if not name:
            raise ValueError(
                "Blood-bank name is missing."
            )

        latitude, longitude, coordinates_valid = (
            self.parse_coordinates(
                row.get("Latitude"),
                row.get("Longitude"),
            )
        )

        if not coordinates_valid:
            statistics["invalid_coordinates"] += 1

        email = self.clean_email(
            row.get("Email")
        )

        if self.clean_text(row.get("Email")) and not email:
            statistics["invalid_emails"] += 1

        website = self.clean_website(
            row.get("Website")
        )

        if (
            self.clean_text(row.get("Website"))
            and not website
        ):
            statistics["invalid_websites"] += 1

        location_values = {
            "address_line": self.clean_text(
                row.get("Address")
            ),
            "locality": "",
            "city": self.clean_text(
                row.get("City")
            ),
            "district": self.clean_text(
                row.get("District")
            ),
            "state": self.clean_text(
                row.get("State")
            ),
            "pincode": self.clean_pincode(
                row.get("Pincode")
            ),
            "latitude": latitude,
            "longitude": longitude,
        }

        bank_values = {
            "name": name,
            "category": self.parse_category(
                row.get("Category")
            ),
            "contact_number": self.clean_text(
                row.get("Contact No")
            ),
            "mobile_number": self.clean_text(
                row.get("Mobile")
            ),
            "helpline": self.clean_text(
                row.get("Helpline")
            ),
            "email": email,
            "website": website,
            "service_time": self.normalize_service_time(
                row.get("Service Time")
            ),
            "license_number": self.clean_text(
                row.get("License #")
            ),
            "blood_component_available": (
                self.parse_boolean(
                    row.get("Blood Component Available")
                )
            ),
            "apheresis_available": self.parse_boolean(
                row.get("Apheresis")
            ),
            "verification_status": (
                BloodBank.VerificationStatus
                .DIRECTORY_IMPORTED
            ),
            "is_active": True,
            "is_public": True,
            "source_metadata": self.build_metadata(row),
        }

        blood_bank = BloodBank.objects.filter(
            source=BloodBank.Source.DIRECTORY_IMPORT,
            source_record_id=source_record_id,
        ).select_related("location").first()

        if blood_bank:
            self.update_location(
                blood_bank.location,
                location_values,
            )

            for field, value in bank_values.items():
                setattr(blood_bank, field, value)

            blood_bank.save()

            return "updated"

        location = Location.objects.create(
            **location_values
        )

        BloodBank.objects.create(
            location=location,
            source=BloodBank.Source.DIRECTORY_IMPORT,
            source_record_id=source_record_id,
            **bank_values,
        )

        return "created"

    @staticmethod
    def clean_column_name(value):
        if value is None:
            return ""

        return re.sub(
            r"\s+",
            " ",
            str(value),
        ).strip()

    def clean_text(self, value):
        if value is None:
            return ""

        cleaned_value = re.sub(
            r"\s+",
            " ",
            str(value),
        ).strip()

        if cleaned_value.lower() in self.NULL_VALUES:
            return ""

        return cleaned_value

    def clean_pincode(self, value):
        cleaned_value = self.clean_text(value)

        if not cleaned_value:
            return ""

        if cleaned_value.endswith(".0"):
            cleaned_value = cleaned_value[:-2]

        digits = re.sub(
            r"\D",
            "",
            cleaned_value,
        )

        if len(digits) == 6:
            return digits

        return cleaned_value[:10]

    def parse_boolean(self, value):
        cleaned_value = self.clean_text(value).lower()

        if cleaned_value in self.TRUE_VALUES:
            return True

        if cleaned_value in self.FALSE_VALUES:
            return False

        return None

    def parse_category(self, value):
        cleaned_value = self.clean_text(value).lower()

        return self.CATEGORY_MAPPING.get(
            cleaned_value,
            BloodBank.Category.OTHER,
        )

    def parse_coordinates(
        self,
        latitude_value,
        longitude_value,
    ):
        latitude_text = self.clean_text(
            latitude_value
        )
        longitude_text = self.clean_text(
            longitude_value
        )

        if not latitude_text and not longitude_text:
            return None, None, True

        try:
            latitude = Decimal(latitude_text)
            longitude = Decimal(longitude_text)
        except (InvalidOperation, ValueError):
            return None, None, False

        indian_coordinate = (
            Decimal("6") <= latitude <= Decimal("38")
            and Decimal("68")
            <= longitude
            <= Decimal("98")
        )

        if not indian_coordinate:
            return None, None, False

        return (
            latitude.quantize(Decimal("0.000001")),
            longitude.quantize(Decimal("0.000001")),
            True,
        )

    def clean_email(self, value):
        cleaned_value = self.clean_text(value).lower()

        if not cleaned_value:
            return ""

        candidates = re.split(
            r"[,;/\s]+",
            cleaned_value,
        )

        validator = EmailValidator()

        for candidate in candidates:
            if not candidate:
                continue

            try:
                validator(candidate)
                return candidate
            except ValidationError:
                continue

        return ""

    def clean_website(self, value):
        cleaned_value = self.clean_text(value)

        if not cleaned_value:
            return ""

        if cleaned_value.lower().startswith("www."):
            cleaned_value = f"https://{cleaned_value}"

        parsed_url = urlparse(cleaned_value)

        if not parsed_url.scheme:
            cleaned_value = f"https://{cleaned_value}"

        validator = URLValidator(
            schemes=["http", "https"],
        )

        try:
            validator(cleaned_value)
        except ValidationError:
            return ""

        return cleaned_value

    def normalize_service_time(self, value):
        cleaned_value = self.clean_text(value)

        if not cleaned_value:
            return ""

        comparison_value = re.sub(
            r"[\s*]",
            "",
            cleaned_value,
        ).lower()

        twenty_four_hour_values = {
            "24x7",
            "24hours",
            "24hrs",
            "24hour",
        }

        if comparison_value in twenty_four_hour_values:
            return "24x7"

        return cleaned_value

    def build_metadata(self, row):
        return {
            "fax": self.clean_text(
                row.get("Fax")
            ),
            "nodal_officer": self.clean_text(
                row.get("Nodal Officer")
            ),
            "nodal_officer_contact": self.clean_text(
                row.get("Contact Nodal Officer")
            ),
            "nodal_officer_mobile": self.clean_text(
                row.get("Mobile Nodal Officer")
            ),
            "nodal_officer_email": self.clean_email(
                row.get("Email Nodal Officer")
            ),
            "nodal_officer_qualification": (
                self.clean_text(
                    row.get(
                        "Qualification Nodal Officer"
                    )
                )
            ),
            "license_obtained_date_raw": self.clean_text(
                row.get("Date License Obtained")
            ),
            "license_renewal_date_raw": self.clean_text(
                row.get("Date of Renewal")
            ),
        }

    @staticmethod
    def update_location(location, values):
        for field, value in values.items():
            setattr(location, field, value)

        location.save()

    @staticmethod
    def _validate_file(csv_path):
        if not csv_path.exists():
            raise CommandError(
                f"CSV file not found: {csv_path}"
            )

        if not csv_path.is_file():
            raise CommandError(
                f"The supplied path is not a file: {csv_path}"
            )

        if csv_path.suffix.lower() != ".csv":
            raise CommandError(
                "The supplied file must have a .csv extension."
            )

    @staticmethod
    def _validate_headers(headers):
        required_headers = {
            "Sr No",
            "Blood Bank Name",
            "State",
            "District",
            "City",
            "Latitude",
            "Longitude",
        }

        missing_headers = required_headers.difference(
            headers
        )

        if missing_headers:
            raise CommandError(
                "Required CSV columns are missing: "
                + ", ".join(sorted(missing_headers))
            )

    def print_summary(self, statistics, dry_run):
        summary_lines = [
            "",
            "Blood-bank import summary",
            "-------------------------",
            (
                f"Processed: "
                f"{statistics['processed']}"
            ),
            f"Created: {statistics['created']}",
            f"Updated: {statistics['updated']}",
            f"Skipped: {statistics['skipped']}",
            (
                "Invalid coordinates converted to null: "
                f"{statistics['invalid_coordinates']}"
            ),
            (
                "Invalid emails removed: "
                f"{statistics['invalid_emails']}"
            ),
            (
                "Invalid websites removed: "
                f"{statistics['invalid_websites']}"
            ),
            f"Errors: {statistics['errors']}",
        ]

        if dry_run:
            summary_lines.append(
                "Result: Dry run completed. "
                "No changes were saved."
            )
        else:
            summary_lines.append(
                "Result: Import completed."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\n".join(summary_lines)
            )
        )