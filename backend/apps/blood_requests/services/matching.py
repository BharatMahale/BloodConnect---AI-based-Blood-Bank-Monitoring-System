from django.core.exceptions import ValidationError
from apps.blood_banks.models import BloodBank
from apps.inventory.models import BloodInventory
from apps.locations.utils.distance import (
    calculate_haversine_distance,
)


def suggest_blood_banks(
    *,
    blood_request,
    radius_km=50,
    limit=10,
):
    """
    Suggest nearby blood banks for a request.

    Ranking:
    1. Full stock availability
    2. Partial stock availability
    3. No reported availability
    4. Shortest distance
    """

    if not blood_request.has_coordinates:
        raise ValidationError(
            "Hospital coordinates are required "
            "for nearby blood-bank suggestions."
        )

    try:
        radius_km = float(radius_km)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "Radius must be a valid number."
        ) from error

    try:
        limit = int(limit)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "Limit must be a whole number."
        ) from error

    if radius_km <= 0:
        raise ValidationError(
            "Radius must be greater than zero."
        )

    if radius_km > 200:
        raise ValidationError(
            "Radius cannot exceed 200 kilometres."
        )

    if limit <= 0 or limit > 50:
        raise ValidationError(
            "Limit must be between 1 and 50."
        )

    public_statuses = {
        BloodBank.VerificationStatus.VERIFIED,
        BloodBank.VerificationStatus
        .DIRECTORY_IMPORTED,
    }

    blood_banks = (
        BloodBank.objects
        .select_related("location")
        .filter(
            is_active=True,
            is_public=True,
            verification_status__in=public_statuses,
            location__latitude__isnull=False,
            location__longitude__isnull=False,
        )
    )

    matching_inventory = (
        BloodInventory.objects
        .filter(
            blood_group=blood_request.blood_group,
            component=blood_request.component,
            blood_bank__in=blood_banks,
        )
        .select_related(
            "blood_bank",
            "blood_group",
            "component",
        )
    )

    inventory_by_bank = {
        inventory.blood_bank_id: inventory
        for inventory in matching_inventory
    }

    required_units = max(
        blood_request.remaining_units,
        0,
    )

    suggestions = []

    for blood_bank in blood_banks:
        distance_km = (
            calculate_haversine_distance(
                latitude_1=(
                    blood_request.hospital_latitude
                ),
                longitude_1=(
                    blood_request.hospital_longitude
                ),
                latitude_2=(
                    blood_bank.location.latitude
                ),
                longitude_2=(
                    blood_bank.location.longitude
                ),
            )
        )

        distance_km = float(distance_km)

        if distance_km > radius_km:
            continue

        inventory = inventory_by_bank.get(
            blood_bank.id
        )

        if inventory:
            available_units = max(
                inventory.total_units
                - inventory.reserved_units,
                0,
            )
        else:
            available_units = 0

        if (
            required_units > 0
            and available_units >= required_units
        ):
            availability_status = (
                "FULLY_AVAILABLE"
            )
            availability_rank = 0
            recommendation_reason = (
                "Enough reported units are available."
            )

        elif available_units > 0:
            availability_status = (
                "PARTIALLY_AVAILABLE"
            )
            availability_rank = 1
            recommendation_reason = (
                "Some reported units are available."
            )

        else:
            availability_status = (
                "NOT_REPORTED_OR_UNAVAILABLE"
            )
            availability_rank = 2
            recommendation_reason = (
                "No matching available stock is "
                "currently reported."
            )

        suggestions.append(
            {
                "blood_bank_id": str(
                    blood_bank.id
                ),
                "name": blood_bank.name,
                "slug": blood_bank.slug,
                "category": blood_bank.category,
                "verification_status": (
                    blood_bank.verification_status
                ),
                "city": (
                    blood_bank.location.city
                ),
                "district": (
                    blood_bank.location.district
                ),
                "state": (
                    blood_bank.location.state
                ),
                "latitude": float(
                    blood_bank.location.latitude
                ),
                "longitude": float(
                    blood_bank.location.longitude
                ),
                "distance_km": round(
                    distance_km,
                    2,
                ),
                "required_units": required_units,
                "available_units": available_units,
                "availability_status": (
                    availability_status
                ),
                "can_fully_fulfil": (
                    availability_status
                    == "FULLY_AVAILABLE"
                ),
                "recommendation_reason": (
                    recommendation_reason
                ),
                "_availability_rank": (
                    availability_rank
                ),
            }
        )

    suggestions.sort(
        key=lambda item: (
            item["_availability_rank"],
            item["distance_km"],
            item["name"].lower(),
        )
    )

    suggestions = suggestions[:limit]

    for suggestion in suggestions:
        suggestion.pop(
            "_availability_rank",
            None,
        )

    return suggestions