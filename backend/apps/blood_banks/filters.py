from django_filters import rest_framework as filters
from .models import BloodBank


class BloodBankFilter(filters.FilterSet):
    state = filters.CharFilter(
        field_name="location__state",
        lookup_expr="iexact",
    )
    district = filters.CharFilter(
        field_name="location__district",
        lookup_expr="iexact",
    )
    city = filters.CharFilter(
        field_name="location__city",
        lookup_expr="iexact",
    )
    pincode = filters.CharFilter(
        field_name="location__pincode",
        lookup_expr="exact",
    )
    category = filters.ChoiceFilter(
        choices=BloodBank.Category.choices,
    )
    component_available = filters.BooleanFilter(
        field_name="blood_component_available",
    )
    apheresis_available = filters.BooleanFilter(
        field_name="apheresis_available",
    )
    verified = filters.BooleanFilter(
        method="filter_verified",
    )
    has_coordinates = filters.BooleanFilter(
        method="filter_has_coordinates",
    )

    class Meta:
        model = BloodBank
        fields = (
            "state",
            "district",
            "city",
            "pincode",
            "category",
            "component_available",
            "apheresis_available",
            "verified",
            "has_coordinates",
        )

    def filter_verified(
        self,
        queryset,
        name,
        value,
    ):
        if value:
            return queryset.filter(
                verification_status=(
                    BloodBank.VerificationStatus.VERIFIED
                )
            )

        return queryset.exclude(
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            )
        )

    def filter_has_coordinates(
        self,
        queryset,
        name,
        value,
    ):
        if value:
            return queryset.filter(
                location__latitude__isnull=False,
                location__longitude__isnull=False,
            )

        return queryset.filter(
            location__latitude__isnull=True,
            location__longitude__isnull=True,
        )