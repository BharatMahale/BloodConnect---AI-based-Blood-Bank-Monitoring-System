from django.utils import timezone
from rest_framework import serializers

from apps.blood_banks.models import BloodBank
from apps.blood_requests.models import (
    BloodRequest,
    BloodRequestBankAssignment,
    BloodRequestReservation,
    BloodRequestStatusHistory,
)
from apps.blood_requests.services import (
    create_blood_request,
)


class BloodRequestStatusHistorySerializer(
    serializers.ModelSerializer
):
    changed_by_email = serializers.EmailField(
        source="changed_by.email",
        read_only=True,
        allow_null=True,
    )

    previous_status_display = serializers.CharField(
        source="get_previous_status_display",
        read_only=True,
    )

    new_status_display = serializers.CharField(
        source="get_new_status_display",
        read_only=True,
    )

    class Meta:
        model = BloodRequestStatusHistory

        fields = [
            "id",
            "previous_status",
            "previous_status_display",
            "new_status",
            "new_status_display",
            "note",
            "changed_by_email",
            "created_at",
        ]

        read_only_fields = fields


class BloodRequestListSerializer(
    serializers.ModelSerializer
):
    blood_bank_name = serializers.CharField(
        source="blood_bank.name",
        read_only=True,
        allow_null=True,
    )

    blood_group_name = serializers.CharField(
        source="blood_group.name",
        read_only=True,
    )

    component_name = serializers.CharField(
        source="component.name",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    urgency_display = serializers.CharField(
        source="get_urgency_display",
        read_only=True,
    )

    remaining_units = serializers.IntegerField(
        read_only=True
    )

    class Meta:
        model = BloodRequest

        fields = [
            "id",
            "request_number",
            "blood_bank",
            "blood_bank_name",
            "blood_group",
            "blood_group_name",
            "component",
            "component_name",
            "units_required",
            "units_fulfilled",
            "remaining_units",
            "hospital_name",
            "required_date",
            "urgency",
            "urgency_display",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class BloodRequestReservationSerializer(
    serializers.ModelSerializer
):
    inventory_blood_bank = serializers.CharField(
        source="inventory.blood_bank.name",
        read_only=True,
    )

    blood_group = serializers.CharField(
        source="inventory.blood_group.name",
        read_only=True,
    )

    component = serializers.CharField(
        source="inventory.component.name",
        read_only=True,
    )

    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
    )

    released_by_email = serializers.EmailField(
        source="released_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = BloodRequestReservation

        fields = [
            "id",
            "inventory",
            "inventory_blood_bank",
            "blood_group",
            "component",
            "reserved_units",
            "fulfilled_units",
            "status",
            "created_by_email",
            "released_by_email",
            "release_reason",
            "released_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class ReserveInventorySerializer(
    serializers.Serializer
):
    quantity = serializers.IntegerField(
        min_value=1
    )


class FulfilInventorySerializer(
    serializers.Serializer
):
    quantity = serializers.IntegerField(
        min_value=1
    )

    note = serializers.CharField(
        max_length=1000,
        required=True,
        allow_blank=False,
    )

    def validate_note(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A fulfilment note is required."
            )

        return value


class ReleaseInventorySerializer(
    serializers.Serializer
):
    reason = serializers.CharField(
        max_length=1000,
        required=True,
        allow_blank=False,
    )

    def validate_reason(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A release reason is required."
            )

        return value


class SuggestedBanksQuerySerializer(
    serializers.Serializer
):
    radius_km = serializers.FloatField(
        min_value=1,
        max_value=200,
        required=False,
        default=50,
    )

    limit = serializers.IntegerField(
        min_value=1,
        max_value=50,
        required=False,
        default=10,
    )


class BloodBankSuggestionSerializer(
    serializers.Serializer
):
    blood_bank_id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    category = serializers.CharField()
    verification_status = serializers.CharField()

    city = serializers.CharField(
        allow_blank=True,
        allow_null=True,
    )

    district = serializers.CharField(
        allow_blank=True,
        allow_null=True,
    )

    state = serializers.CharField(
        allow_blank=True,
        allow_null=True,
    )

    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    distance_km = serializers.FloatField()
    required_units = serializers.IntegerField()
    available_units = serializers.IntegerField()
    availability_status = serializers.CharField()
    can_fully_fulfil = serializers.BooleanField()
    recommendation_reason = serializers.CharField()


class AssignBloodBankSerializer(
    serializers.Serializer
):
    blood_bank = serializers.PrimaryKeyRelatedField(
        queryset=BloodBank.objects.all()
    )

    reason = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default="",
    )


class BloodRequestBankAssignmentSerializer(
    serializers.ModelSerializer
):
    previous_blood_bank_name = (
        serializers.CharField(
            source="previous_blood_bank.name",
            read_only=True,
            allow_null=True,
        )
    )

    new_blood_bank_name = serializers.CharField(
        source="new_blood_bank.name",
        read_only=True,
    )

    assigned_by_email = serializers.EmailField(
        source="assigned_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = BloodRequestBankAssignment

        fields = [
            "id",
            "previous_blood_bank",
            "previous_blood_bank_name",
            "new_blood_bank",
            "new_blood_bank_name",
            "assigned_by_email",
            "reason",
            "created_at",
        ]

        read_only_fields = fields


class BloodRequestDetailSerializer(
    serializers.ModelSerializer
):
    requester_email = serializers.EmailField(
        source="requester.email",
        read_only=True,
    )

    blood_bank_name = serializers.CharField(
        source="blood_bank.name",
        read_only=True,
        allow_null=True,
    )

    blood_group_name = serializers.CharField(
        source="blood_group.name",
        read_only=True,
    )

    component_name = serializers.CharField(
        source="component.name",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    urgency_display = serializers.CharField(
        source="get_urgency_display",
        read_only=True,
    )

    remaining_units = serializers.IntegerField(
        read_only=True
    )

    status_history = (
        BloodRequestStatusHistorySerializer(
            many=True,
            read_only=True,
        )
    )

    reservation = (
        BloodRequestReservationSerializer(
            read_only=True
        )
    )

    assignment_history = (
        BloodRequestBankAssignmentSerializer(
            many=True,
            read_only=True,
        )
    )

    class Meta:
        model = BloodRequest

        fields = [
            "id",
            "request_number",
            "requester_email",
            "blood_bank",
            "blood_bank_name",
            "blood_group",
            "blood_group_name",
            "component",
            "component_name",
            "patient_name",
            "units_required",
            "units_fulfilled",
            "remaining_units",
            "hospital_name",
            "hospital_address",
            "hospital_latitude",
            "hospital_longitude",
            "contact_phone",
            "required_date",
            "urgency",
            "urgency_display",
            "status",
            "status_display",
            "additional_information",
            "blood_bank_response",
            "reviewed_at",
            "expires_at",
            "created_at",
            "updated_at",
            "reservation",
            "assignment_history",
            "status_history",
        ]

        read_only_fields = fields


class BloodRequestCreateSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = BloodRequest

        fields = [
            "blood_bank",
            "blood_group",
            "component",
            "patient_name",
            "units_required",
            "hospital_name",
            "hospital_address",
            "hospital_latitude",
            "hospital_longitude",
            "contact_phone",
            "required_date",
            "urgency",
            "additional_information",
        ]

        extra_kwargs = {
            "blood_bank": {
                "required": False,
                "allow_null": True,
            },
            "additional_information": {
                "required": False,
                "allow_blank": True,
            },
        }

    def validate_required_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError(
                "Required date cannot be in the past."
            )

        return value

    def validate_blood_bank(self, blood_bank):
        if blood_bank is None:
            return blood_bank

        public_statuses = {
            BloodBank.VerificationStatus.VERIFIED,
            BloodBank.VerificationStatus.DIRECTORY_IMPORTED,
        }

        if not blood_bank.is_active:
            raise serializers.ValidationError(
                "The selected blood bank is inactive."
            )

        if not blood_bank.is_public:
            raise serializers.ValidationError(
                "The selected blood bank is not "
                "publicly available."
            )

        if (
            blood_bank.verification_status
            not in public_statuses
        ):
            raise serializers.ValidationError(
                "The selected blood bank is not verified."
            )

        return blood_bank

    def create(self, validated_data):
        request = self.context["request"]

        return create_blood_request(
            requester=request.user,
            request_data=validated_data,
        )

    def validate(self, attrs):
        latitude = attrs.get(
            "hospital_latitude"
        )
        longitude = attrs.get(
            "hospital_longitude"
        )

        only_one_coordinate = (
            latitude is None
        ) != (
            longitude is None
        )

        if only_one_coordinate:
            raise serializers.ValidationError(
                {
                    "location": (
                        "Hospital latitude and longitude "
                        "must be provided together."
                    )
                }
            )

        return attrs


class BloodRequestStatusUpdateSerializer(
    serializers.Serializer
):
    new_status = serializers.ChoiceField(
        choices=BloodRequest.Status.choices
    )

    units_fulfilled = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )

    note = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default="",
    )


class BloodRequestCancelSerializer(
    serializers.Serializer
):
    reason = serializers.CharField(
        max_length=1000,
        required=True,
        allow_blank=False,
    )

    def validate_reason(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A cancellation reason is required."
            )

        return value