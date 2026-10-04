from django.test import SimpleTestCase
from apps.locations.utils.distance import (
    calculate_bounding_box,
    calculate_haversine_distance,
)


class DistanceUtilityTests(SimpleTestCase):
    def test_same_location_has_zero_distance(self):
        distance = calculate_haversine_distance(
            latitude_1=21.349,
            longitude_1=74.879,
            latitude_2=21.349,
            longitude_2=74.879,
        )

        self.assertAlmostEqual(
            distance,
            0.0,
            places=5,
        )

    def test_nearest_test_bank_is_within_radius(self):
        distance = calculate_haversine_distance(
            latitude_1=21.349,
            longitude_1=74.879,
            latitude_2=21.350,
            longitude_2=74.880,
        )

        self.assertGreater(distance, 0)
        self.assertLess(distance, 1)

    def test_second_test_bank_is_within_radius(self):
        distance = calculate_haversine_distance(
            latitude_1=21.349,
            longitude_1=74.879,
            latitude_2=21.370,
            longitude_2=74.890,
        )

        self.assertGreater(distance, 2)
        self.assertLess(distance, 4)

    def test_dhule_is_outside_ten_kilometres(self):
        distance = calculate_haversine_distance(
            latitude_1=21.349,
            longitude_1=74.879,
            latitude_2=20.9042,
            longitude_2=74.7749,
        )

        self.assertGreater(distance, 45)
        self.assertLess(distance, 60)

    def test_bounding_box_contains_origin(self):
        bounding_box = calculate_bounding_box(
            latitude=21.349,
            longitude=74.879,
            radius_km=10,
        )

        self.assertLess(
            bounding_box.minimum_latitude,
            21.349,
        )
        self.assertGreater(
            bounding_box.maximum_latitude,
            21.349,
        )
        self.assertLess(
            bounding_box.minimum_longitude,
            74.879,
        )
        self.assertGreater(
            bounding_box.maximum_longitude,
            74.879,
        )