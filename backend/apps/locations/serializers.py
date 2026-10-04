from rest_framework import serializers
from .models import Location


class LocationSerializer(serializers.ModelSerializer):
    has_coordinates = serializers.BooleanField(
        read_only=True,
    )

    class Meta:
        model = Location
        fields = (
            "id",
            "address_line",
            "locality",
            "city",
            "district",
            "state",
            "pincode",
            "latitude",
            "longitude",
            "has_coordinates",
            "full_address",
        )
        read_only_fields = (
            "id",
            "has_coordinates",
            "full_address",
        )

    def validate(self, attributes):
        instance = self.instance

        latitude = attributes.get(
            "latitude",
            getattr(instance, "latitude", None),
        )
        longitude = attributes.get(
            "longitude",
            getattr(instance, "longitude", None),
        )

        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                "Latitude and longitude must be provided together."
            )

        return attributes