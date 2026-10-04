from apps.locations.utils.distance import (
    calculate_haversine_distance,
)
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.blood_banks.models import BloodBank
from apps.locations.models import Location


class NearbyBloodBankAPITests(APITestCase):
    def create_bank(
        self,
        name,
        latitude,
        longitude,
        status_value=None,
        category=BloodBank.Category.GOVERNMENT,
    ):
        location = Location.objects.create(
            address_line=f"{name} Road",
            city="Shirpur",
            district="Dhule",
            state="Maharashtra",
            latitude=latitude,
            longitude=longitude,
        )

        return BloodBank.objects.create(
            name=name,
            location=location,
            category=category,
            source=BloodBank.Source.DIRECTORY_IMPORT,
            verification_status=(
                status_value
                or BloodBank.VerificationStatus
                .DIRECTORY_IMPORTED
            ),
        )

    def setUp(self):
        self.url = reverse(
            "blood_banks:blood-bank-nearby"
        )

        self.nearest_bank = self.create_bank(
            name="Nearest Blood Bank",
            latitude="21.350000",
            longitude="74.880000",
        )

        self.second_bank = self.create_bank(
            name="Second Blood Bank",
            latitude="21.370000",
            longitude="74.890000",
        )

        self.distant_bank = self.create_bank(
            name="Distant Blood Bank",
            latitude="20.904200",
            longitude="74.774900",
        )

        location_without_coordinates = (
            Location.objects.create(
                city="Shirpur",
                district="Dhule",
                state="Maharashtra",
            )
        )

        BloodBank.objects.create(
            name="Unknown Location Bank",
            location=location_without_coordinates,
            source=BloodBank.Source.DIRECTORY_IMPORT,
            verification_status=(
                BloodBank.VerificationStatus
                .DIRECTORY_IMPORTED
            ),
        )

    def test_public_user_can_search_nearby_banks(self):
        response = self.client.get(
            self.url,
            {
                "latitude": 21.349,
                "longitude": 74.879,
                "radius_km": 10,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["count"],
            2,
        )

    def test_results_are_sorted_by_distance(self):
        response = self.client.get(
            self.url,
            {
                "latitude": 21.349,
                "longitude": 74.879,
                "radius_km": 10,
            },
        )

        results = response.data["results"]

        self.assertEqual(
            len(results),
            2,
        )
        self.assertEqual(
            results[0]["name"],
            "Nearest Blood Bank",
        )
        self.assertEqual(
            results[1]["name"],
            "Second Blood Bank",
        )
        self.assertLessEqual(
            results[0]["distance_km"],
            results[1]["distance_km"],
        )

    def test_distant_bank_is_excluded(self):
        response = self.client.get(
            self.url,
            {
                "latitude": 21.349,
                "longitude": 74.879,
                "radius_km": 10,
            },
        )

        returned_names = [
            bank["name"]
            for bank in response.data["results"]
        ]

        self.assertNotIn(
            "Distant Blood Bank",
            returned_names,
        )

    def test_missing_coordinates_are_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            "latitude",
            response.data,
        )
        self.assertIn(
            "longitude",
            response.data,
        )

    def test_radius_greater_than_limit_is_rejected(self):
        response = self.client.get(
            self.url,
            {
                "latitude": 21.349,
                "longitude": 74.879,
                "radius_km": 500,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_verified_filter_returns_verified_banks(self):
        self.nearest_bank.verification_status = (
            BloodBank.VerificationStatus.VERIFIED
        )
        self.nearest_bank.save()

        response = self.client.get(
            self.url,
            {
                "latitude": 21.349,
                "longitude": 74.879,
                "radius_km": 10,
                "verified_only": "true",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertEqual(
            response.data["results"][0]["name"],
            "Nearest Blood Bank",
        )

    def test_test_banks_are_publicly_visible(self):
        visible_banks = BloodBank.objects.filter(
            is_active=True,
            is_public=True,
            verification_status__in=[
                BloodBank.VerificationStatus.VERIFIED,
                BloodBank.VerificationStatus
                .DIRECTORY_IMPORTED,
            ],
            location__latitude__isnull=False,
            location__longitude__isnull=False,
        )

        self.assertEqual(
            visible_banks.count(),
            3,
        )

    def test_coordinate_banks_exist_before_search(self):
        banks = BloodBank.objects.filter(
            is_active=True,
            is_public=True,
            verification_status__in=[
                BloodBank.VerificationStatus.VERIFIED,
                BloodBank.VerificationStatus
                .DIRECTORY_IMPORTED,
            ],
            location__latitude__isnull=False,
            location__longitude__isnull=False,
        )

        self.assertEqual(
            banks.count(),
            3,
        )

        coordinates = list(
            banks.values_list(
                "location__latitude",
                "location__longitude",
            )
        )

        self.assertEqual(
            len(coordinates),
            3,
        )

    def test_created_bank_distances_are_correct(self):
        nearest_distance = (
            calculate_haversine_distance(
                latitude_1=21.349,
                longitude_1=74.879,
                latitude_2=(
                    self.nearest_bank.location.latitude
                ),
                longitude_2=(
                    self.nearest_bank.location.longitude
                ),
            )
        )

        second_distance = (
            calculate_haversine_distance(
                latitude_1=21.349,
                longitude_1=74.879,
                latitude_2=(
                    self.second_bank.location.latitude
                ),
                longitude_2=(
                    self.second_bank.location.longitude
                ),
            )
        )

        distant_distance = (
            calculate_haversine_distance(
                latitude_1=21.349,
                longitude_1=74.879,
                latitude_2=(
                    self.distant_bank.location.latitude
                ),
                longitude_2=(
                    self.distant_bank.location.longitude
                ),
            )
        )

        self.assertLess(nearest_distance, 1)
        self.assertLess(second_distance, 10)
        self.assertGreater(distant_distance, 10)

    def test_component_filter_is_only_applied_when_given(self):
        self.nearest_bank.blood_component_available = True
        self.nearest_bank.save()

        self.second_bank.blood_component_available = False
        self.second_bank.save()

        response = self.client.get(
            self.url,
            {
                "latitude": 21.349,
                "longitude": 74.879,
                "radius_km": 10,
                "component_available": "true",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertEqual(
            response.data["results"][0]["name"],
            "Nearest Blood Bank",
        )


    def test_apheresis_filter_is_only_applied_when_given(self):
        self.nearest_bank.apheresis_available = True
        self.nearest_bank.save()

        self.second_bank.apheresis_available = False
        self.second_bank.save()

        response = self.client.get(
            self.url,
            {
                "latitude": 21.349,
                "longitude": 74.879,
                "radius_km": 10,
                "apheresis_available": "true",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertEqual(
            response.data["results"][0]["name"],
            "Nearest Blood Bank",
        )