from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt


EARTH_RADIUS_KM = 6371.0088
APPROXIMATE_KM_PER_LATITUDE_DEGREE = 111.0


@dataclass(frozen=True)
class BoundingBox:
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float


def calculate_haversine_distance(
    latitude_1,
    longitude_1,
    latitude_2,
    longitude_2,
):
    """
    Calculate the distance between two points in kilometres.

    Parameters must be supplied in this order:
    latitude 1, longitude 1, latitude 2, longitude 2.
    """

    lat_1 = radians(float(latitude_1))
    lon_1 = radians(float(longitude_1))
    lat_2 = radians(float(latitude_2))
    lon_2 = radians(float(longitude_2))

    latitude_difference = lat_2 - lat_1
    longitude_difference = lon_2 - lon_1

    a = (
        sin(latitude_difference / 2.0) ** 2
        + cos(lat_1)
        * cos(lat_2)
        * sin(longitude_difference / 2.0) ** 2
    )

    a = min(1.0, max(0.0, a))

    central_angle = 2.0 * asin(sqrt(a))

    distance_km = EARTH_RADIUS_KM * central_angle

    return float(distance_km)


def calculate_bounding_box(
    latitude,
    longitude,
    radius_km,
):
    """Calculate an approximate geographic bounding box."""

    latitude = float(latitude)
    longitude = float(longitude)
    radius_km = float(radius_km)

    latitude_delta = (
        radius_km
        / APPROXIMATE_KM_PER_LATITUDE_DEGREE
    )

    longitude_scale = abs(
        cos(radians(latitude))
    )

    if longitude_scale < 0.01:
        longitude_delta = 180.0
    else:
        longitude_delta = (
            radius_km
            / (
                APPROXIMATE_KM_PER_LATITUDE_DEGREE
                * longitude_scale
            )
        )

    return BoundingBox(
        minimum_latitude=max(
            -90.0,
            latitude - latitude_delta,
        ),
        maximum_latitude=min(
            90.0,
            latitude + latitude_delta,
        ),
        minimum_longitude=max(
            -180.0,
            longitude - longitude_delta,
        ),
        maximum_longitude=min(
            180.0,
            longitude + longitude_delta,
        ),
    )