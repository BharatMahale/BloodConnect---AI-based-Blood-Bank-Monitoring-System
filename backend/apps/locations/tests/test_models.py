from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from apps.locations.models import Location


class LocationModelTests(TestCase):
    def test_location_can_be_created(self):
        location = Location.objects.create(
            address_line="R. C. Patel Institute Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            pincode="425405",
            latitude=Decimal("21.349000"),
            longitude=Decimal("74.879000"),
        )

        self.assertEqual(
            str(location),
            "Shirpur, Dhule, Maharashtra",
        )
        self.assertTrue(location.has_coordinates)
        self.assertTrue(
            location.has_valid_indian_coordinates
        )

    def test_both_coordinates_are_required_together(self):
        location = Location(
            city="Shirpur",
            state="Maharashtra",
            latitude=Decimal("21.349000"),
            longitude=None,
        )

        with self.assertRaises(ValidationError):
            location.full_clean()

    def test_location_without_coordinates_is_allowed(self):
        location = Location(
            city="Dhule",
            district="Dhule",
            state="Maharashtra",
        )

        location.full_clean()

        self.assertFalse(location.has_coordinates)