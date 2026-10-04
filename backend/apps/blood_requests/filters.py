import django_filters

from apps.blood_requests.models import (
    BloodRequest,
)


class BloodRequestFilter(
    django_filters.FilterSet
):
    assigned_to_my_bank = django_filters.BooleanFilter(
        method="filter_assigned_to_my_bank",
    )
    status = django_filters.ChoiceFilter(
        choices=BloodRequest.Status.choices
    )

    urgency = django_filters.ChoiceFilter(
        choices=BloodRequest.Urgency.choices
    )

    blood_bank = django_filters.UUIDFilter(
        field_name="blood_bank_id"
    )

    blood_group = django_filters.UUIDFilter(
        field_name="blood_group_id"
    )

    component = django_filters.UUIDFilter(
        field_name="component_id"
    )

    required_from = django_filters.DateFilter(
        field_name="required_date",
        lookup_expr="gte",
    )

    required_to = django_filters.DateFilter(
        field_name="required_date",
        lookup_expr="lte",
    )

    request_number = django_filters.CharFilter(
        field_name="request_number",
        lookup_expr="iexact",
    )

    class Meta:
        model = BloodRequest

        fields = (
            "status",
            "urgency",
            "blood_bank",
            "blood_group",
            "component",
            "request_number",
            "required_from",
            "required_to",
            "assigned_to_my_bank",
        )

    def filter_assigned_to_my_bank(
        self,
        queryset,
        name,
        value,
    ):
        if value is not True:
            return queryset

        user = getattr(self.request, "user", None)

        if not user or not user.is_authenticated:
            return queryset.none()

        return queryset.filter(
            blood_bank__owner=user,
        )
