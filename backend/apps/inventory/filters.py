import django_filters

from .models import BloodInventory


class BloodInventoryFilter(django_filters.FilterSet):
    blood_bank = django_filters.UUIDFilter(
        field_name="blood_bank_id"
    )
    blood_group = django_filters.UUIDFilter(
        field_name="blood_group_id"
    )
    component = django_filters.UUIDFilter(
        field_name="component_id"
    )
    owned = django_filters.BooleanFilter(
        method="filter_owned",
    )
    city = django_filters.CharFilter(
        field_name="blood_bank__city",
        lookup_expr="iexact",
    )
    minimum_units = django_filters.NumberFilter(
        field_name="total_units",
        lookup_expr="gte",
    )
    available = django_filters.BooleanFilter(
        method="filter_available",
    )

    class Meta:
        model = BloodInventory
        fields = (
            "blood_bank",
            "blood_group",
            "component",
            "city",
            "minimum_units",
            "available",
            "owned",
        )

    def filter_owned(self, queryset, name, value):
        if value is not True:
            return queryset

        user = getattr(self.request, "user", None)

        if not user or not user.is_authenticated:
            return queryset.none()

        return queryset.filter(
            blood_bank__owner=user,
        )

    def filter_available(
        self,
        queryset,
        name,
        value,
    ):
        if value is True:
            return queryset.filter(
                available_units__gt=0
            )

        if value is False:
            return queryset.filter(
                available_units=0
            )

        return queryset
