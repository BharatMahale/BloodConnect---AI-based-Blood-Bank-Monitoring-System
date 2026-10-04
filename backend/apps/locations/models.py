import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Location(models.Model):
    """Reusable address and geographic location."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    address_line = models.TextField(blank=True)
    locality = models.CharField(
        max_length=150,
        blank=True,
    )
    city = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
    )
    district = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
    )
    state = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
    )
    pincode = models.CharField(
        max_length=10,
        blank=True,
        db_index=True,
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-90")),
            MaxValueValidator(Decimal("90")),
        ],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-180")),
            MaxValueValidator(Decimal("180")),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "state",
            "district",
            "city",
        ]
        indexes = [
            models.Index(
                fields=["state", "district", "city"],
                name="location_area_idx",
            ),
            models.Index(
                fields=["latitude", "longitude"],
                name="location_coordinates_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True)
                    | Q(
                        latitude__gte=Decimal("-90"),
                        latitude__lte=Decimal("90"),
                    )
                ),
                name="valid_latitude_range",
            ),
            models.CheckConstraint(
                condition=(
                    Q(longitude__isnull=True)
                    | Q(
                        longitude__gte=Decimal("-180"),
                        longitude__lte=Decimal("180"),
                    )
                ),
                name="valid_longitude_range",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        latitude__isnull=True,
                        longitude__isnull=True,
                    )
                    | Q(
                        latitude__isnull=False,
                        longitude__isnull=False,
                    )
                ),
                name="coordinate_pair_required",
            ),
        ]

    def __str__(self):
        parts = [
            self.city,
            self.district,
            self.state,
        ]

        return ", ".join(
            part for part in parts if part
        ) or "Location not specified"

    def clean(self):
        super().clean()

        latitude_exists = self.latitude is not None
        longitude_exists = self.longitude is not None

        if latitude_exists != longitude_exists:
            raise ValidationError(
                {
                    "latitude": (
                        "Latitude and longitude must be "
                        "provided together."
                    ),
                    "longitude": (
                        "Latitude and longitude must be "
                        "provided together."
                    ),
                }
            )

    @property
    def has_coordinates(self):
        return (
            self.latitude is not None
            and self.longitude is not None
        )

    @property
    def has_valid_indian_coordinates(self):
        if not self.has_coordinates:
            return False

        return (
            Decimal("6") <= self.latitude <= Decimal("38")
            and Decimal("68")
            <= self.longitude
            <= Decimal("98")
        )

    @property
    def full_address(self) -> str:
        parts = [
            self.address_line,
            self.locality,
            self.city,
            self.district,
            self.state,
            self.pincode,
        ]

        return ", ".join(
            str(part).strip()
            for part in parts
            if part and str(part).strip()
        )
