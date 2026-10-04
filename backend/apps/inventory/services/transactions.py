from django.core.exceptions import ValidationError
from django.db import transaction
from apps.inventory.models import (
    BloodInventory,
    InventoryTransaction,
)


ADDITION_TYPES = {
    InventoryTransaction.Type.DONATION,
    InventoryTransaction.Type.RECEIVED,
    InventoryTransaction.Type.TRANSFER_IN,
}

REDUCTION_TYPES = {
    InventoryTransaction.Type.ISSUED,
    InventoryTransaction.Type.EXPIRED,
    InventoryTransaction.Type.TRANSFER_OUT,
}


@transaction.atomic
def record_inventory_transaction(*, inventory, transaction_type, quantity, reason, created_by, reference_number="",):
    """
    Apply a stock movement and create its audit record.

    The supplied quantity must always be positive.
    The service determines whether to add or subtract it.
    """

    if not created_by or not created_by.is_authenticated:
        raise ValidationError(
            "An authenticated user is required."
        )

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "Quantity must be a whole number."
        ) from error

    if quantity <= 0:
        raise ValidationError(
            "Quantity must be greater than zero."
        )

    reason = str(reason).strip()

    if not reason:
        raise ValidationError(
            "A transaction reason is required."
        )

    valid_types = {
        choice
        for choice, label
        in InventoryTransaction.Type.choices
    }

    if transaction_type not in valid_types:
        raise ValidationError(
            "Invalid inventory transaction type."
        )

    locked_inventory = (
        BloodInventory.objects.select_for_update()
        .select_related(
            "blood_bank",
            "blood_group",
            "component",
        )
        .get(pk=inventory.pk)
    )

    quantity_before = locked_inventory.total_units

    if transaction_type in ADDITION_TYPES:
        quantity_change = quantity

    elif transaction_type in REDUCTION_TYPES:
        quantity_change = -quantity

    else:
        raise ValidationError(
            "Use the separate adjustment service for "
            "inventory adjustments."
        )

    quantity_after = (
        quantity_before + quantity_change
    )

    if quantity_after < 0:
        raise ValidationError(
            "This transaction would make inventory "
            "negative."
        )

    if quantity_after < locked_inventory.reserved_units:
        raise ValidationError(
            "This transaction would reduce total stock "
            "below the reserved quantity."
        )

    inventory_transaction = (
        InventoryTransaction.objects.create(
            inventory=locked_inventory,
            transaction_type=transaction_type,
            quantity_change=quantity_change,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            reason=reason,
            reference_number=(
                str(reference_number).strip()
            ),
            created_by=created_by,
        )
    )

    locked_inventory.total_units = quantity_after
    locked_inventory.last_updated_by = created_by
    locked_inventory.save(
        update_fields=[
            "total_units",
            "last_updated_by",
            "last_updated_at",
        ]
    )

    return inventory_transaction
@transaction.atomic
def adjust_inventory(
    *,
    inventory,
    new_total_units,
    reason,
    created_by,
    reference_number="",
):
    """Set an audited corrected inventory total."""

    if not created_by or not created_by.is_authenticated:
        raise ValidationError(
            "An authenticated user is required."
        )

    try:
        new_total_units = int(new_total_units)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "New total must be a whole number."
        ) from error

    if new_total_units < 0:
        raise ValidationError(
            "New total cannot be negative."
        )

    reason = str(reason).strip()

    if not reason:
        raise ValidationError(
            "An adjustment reason is required."
        )

    locked_inventory = (
        BloodInventory.objects.select_for_update()
        .get(pk=inventory.pk)
    )

    if new_total_units < locked_inventory.reserved_units:
        raise ValidationError(
            "New total cannot be less than reserved units."
        )

    quantity_before = locked_inventory.total_units
    quantity_change = (
        new_total_units - quantity_before
    )

    if quantity_change == 0:
        raise ValidationError(
            "The new total is the same as the current total."
        )

    inventory_transaction = (
        InventoryTransaction.objects.create(
            inventory=locked_inventory,
            transaction_type=(
                InventoryTransaction.Type.ADJUSTMENT
            ),
            quantity_change=quantity_change,
            quantity_before=quantity_before,
            quantity_after=new_total_units,
            reason=reason,
            reference_number=(
                str(reference_number).strip()
            ),
            created_by=created_by,
        )
    )

    locked_inventory.total_units = new_total_units
    locked_inventory.last_updated_by = created_by
    locked_inventory.save(
        update_fields=[
            "total_units",
            "last_updated_by",
            "last_updated_at",
        ]
    )

    return inventory_transaction
