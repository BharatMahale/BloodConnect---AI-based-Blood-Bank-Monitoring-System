from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from . import geocoding


class AddressQuerySerializer(serializers.Serializer):
    address = serializers.CharField(max_length=250, trim_whitespace=True, allow_blank=False)


class CoordinatesQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class GeocodeResultSerializer(serializers.Serializer):
    address = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class GeocodingThrottle(AnonRateThrottle):
    scope = "geocoding"


class AuthGeocodingThrottle(UserRateThrottle):
    scope = "geocoding_user"


class BaseGeocodeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [GeocodingThrottle, AuthGeocodingThrottle]

    def resolve(self, lookup):
        try:
            result = lookup()
        except geocoding.GeocodingBusy:
            return Response({"detail": "Location lookup is busy. Please try again shortly."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except geocoding.GeocodingUnavailable:
            return Response({"detail": "Location lookup is temporarily unavailable. Please try again."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if result is None:
            return Response({"detail": "We couldn't find that location. Please check the address and try again."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result)


class ForwardGeocodeView(BaseGeocodeView):
    @extend_schema(request=AddressQuerySerializer, responses=GeocodeResultSerializer)
    def post(self, request):
        serializer = AddressQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.resolve(lambda: geocoding.forward(serializer.validated_data["address"]))


class ReverseGeocodeView(BaseGeocodeView):
    @extend_schema(request=CoordinatesQuerySerializer, responses=GeocodeResultSerializer)
    def post(self, request):
        serializer = CoordinatesQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return self.resolve(lambda: geocoding.reverse(data["latitude"], data["longitude"]))
