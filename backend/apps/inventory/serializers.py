from django.db import transaction
from rest_framework import serializers
from apps.blood_banks.models import BloodBank
from .models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)


class BloodGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodGroup
        fields = [
            "id",
            "name",
        ]
        read_only_fields = fields


class BloodComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodComponent
        fields = [
            "id",
            "name",
        ]
        read_only_fields = fields


class InventoryBloodBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodBank
        fields = [
            "id",
            "name",
            "city",
            "state",
        ]
        read_only_fields = fields


class BloodInventorySerializer(
    serializers.ModelSerializer
):
    blood_bank_name = serializers.CharField(
        source="blood_bank.name",
        read_only=True,
    )

    blood_group_name = serializers.CharField(
        source="blood_group.name",
        read_only=True,
    )

    component_name = serializers.CharField(
        source="component.name",
        read_only=True,
    )

    available_units = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = BloodInventory

        fields = [
            "id",
            "blood_bank",
            "blood_bank_name",
            "blood_group",
            "blood_group_name",
            "component",
            "component_name",
            "total_units",
            "reserved_units",
            "available_units",
            "last_updated_at",
        ]

        read_only_fields = [
            "id",
            "total_units",
            "reserved_units",
            "available_units",
            "last_updated_at",
        ]

    def get_available_units(self, obj) -> int:
        return (
            obj.total_units
            - obj.reserved_units
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        can_view_reserved_units = (
            self.context.get(
                "can_view_all_reserved_units",
                False,
            )
            or bool(
                user
                and user.is_authenticated
                and instance.blood_bank.owner_id
                == user.id
            )
        )

        if not can_view_reserved_units:
            representation.pop("reserved_units", None)

        return representation


class InventoryTransactionSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
    )

    transaction_type_display = (
        serializers.CharField(
            source="get_transaction_type_display",
            read_only=True,
        )
    )

    class Meta:
        model = InventoryTransaction

        fields = [
            "id",
            "inventory",
            "transaction_type",
            "transaction_type_display",
            "quantity_change",
            "quantity_before",
            "quantity_after",
            "reason",
            "reference_number",
            "created_by",
            "created_by_email",
            "created_at",
        ]

        read_only_fields = fields


class StockUpdateSerializer(serializers.Serializer):
    transaction_type = serializers.ChoiceField(
        choices=InventoryTransaction.Type.choices
    )

    quantity = serializers.IntegerField(
        min_value=0
    )

    reason = serializers.CharField(
        max_length=500,
        required=True,
        allow_blank=False,
    )

    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_reason(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A transaction reason is required."
            )

        return value

    def validate(self, attrs):
        transaction_type = attrs[
            "transaction_type"
        ]
        quantity = attrs["quantity"]

        if (
            transaction_type
            != InventoryTransaction.Type.ADJUSTMENT
            and quantity <= 0
        ):
            raise serializers.ValidationError(
                {
                    "quantity": (
                        "Quantity must be greater "
                        "than zero."
                    )
                }
            )

        return attrs
