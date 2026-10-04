from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.locations import geocoding


class GeocodingAPITests(APITestCase):
    def setUp(self):
        cache.clear()

    @patch("apps.locations.geocoding.forward")
    def test_forward_success_and_normal_contract(self, lookup):
        lookup.return_value = {"address": "Shirpur, Maharashtra, India", "latitude": 21.349, "longitude": 74.879}
        response = self.client.post(reverse("locations:geocode"), {"address": " Shirpur "})
        self.assertEqual(response.status_code, 200)
        lookup.assert_called_once_with("Shirpur")
        self.assertEqual(set(response.data), {"address", "latitude", "longitude"})

    @patch("apps.locations.geocoding.forward", return_value=None)
    def test_forward_no_result(self, _lookup):
        response = self.client.post(reverse("locations:geocode"), {"address": "Unknown place"})
        self.assertEqual(response.status_code, 404)

    @patch("apps.locations.geocoding.reverse")
    def test_reverse_success(self, lookup):
        lookup.return_value = {"address": "Shirpur, India", "latitude": 21.349, "longitude": 74.879}
        response = self.client.post(reverse("locations:reverse-geocode"), {"latitude": 21.349, "longitude": 74.879})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["address"], "Shirpur, India")

    @patch("apps.locations.geocoding.reverse", return_value=None)
    def test_reverse_no_result(self, _lookup):
        response = self.client.post(reverse("locations:reverse-geocode"), {"latitude": 21.349, "longitude": 74.879})
        self.assertEqual(response.status_code, 404)

    def test_invalid_address(self):
        for value in (" ", "x" * 251):
            response = self.client.post(reverse("locations:geocode"), {"address": value})
            self.assertEqual(response.status_code, 400)

    def test_invalid_coordinates(self):
        for coordinates in ({"latitude": 91, "longitude": 74}, {"latitude": 21, "longitude": -181}, {"latitude": 21}):
            response = self.client.post(reverse("locations:reverse-geocode"), coordinates)
            self.assertEqual(response.status_code, 400)

    @patch("apps.locations.geocoding.forward", side_effect=geocoding.GeocodingUnavailable)
    def test_provider_failure_is_safe(self, _lookup):
        response = self.client.post(reverse("locations:geocode"), {"address": "Shirpur"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("nominatim", str(response.data).lower())


class GeocodingAdapterTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("apps.locations.geocoding._request")
    def test_provider_response_is_normalized_and_cached(self, request):
        request.return_value = [{"display_name": "Shirpur, India", "lat": "21.349", "lon": "74.879", "place_id": 123, "osm_type": "node"}]
        first = geocoding.forward("Shirpur")
        second = geocoding.forward("Shirpur")
        self.assertEqual(first, second)
        self.assertEqual(first, {"address": "Shirpur, India", "latitude": 21.349, "longitude": 74.879})
        request.assert_called_once()

    @patch("apps.locations.geocoding._request")
    def test_reverse_uses_browser_coordinates_without_caching(self, request):
        request.return_value = {"display_name": "Shirpur, India", "lat": "21.35", "lon": "74.88", "place_id": 123}
        result = geocoding.reverse(21.349, 74.879)
        self.assertEqual(result, {"address": "Shirpur, India", "latitude": 21.349, "longitude": 74.879})
        self.assertIsNone(cache.get("geocoding:reverse:21.349:74.879"))
