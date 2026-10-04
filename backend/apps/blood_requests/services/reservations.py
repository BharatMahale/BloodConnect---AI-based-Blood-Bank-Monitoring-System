from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.blood_requests.models import (
    BloodRequest,
    BloodRequestReservation,
)
from apps.blood_requests.services.workflow import (
    transition_blood_request,
)
from apps.inventory.models import (
    BloodInventory,
    InventoryTransaction,
)
from apps.inventory.services.transactions import (
    record_inventory_transaction,
)
from apps.notifications.models import Notification
from apps.notifications.services import (
    notify_requester,
)


def _validate_authenticated_user(
    user,
    *,
    system_operation=False,
):
    authenticated_actor = bool(
        user
        and user.is_authenticated
    )

    if (
        not authenticated_actor
        and not system_operation
    ):
        raise ValidationError(
            "An authenticated user is required."
        )


@transaction.atomic
def reserve_inventory_for_request(
    *,
    blood_request,
    quantity,
    created_by,
):
    """
    Reserve inventory without reducing total stock.
    """

    _validate_authenticated_user(created_by)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "Reservation quantity must be a whole number."
        ) from error

    if quantity <= 0:
        raise ValidationError(
            "Reservation quantity must be greater than zero."
        )

    locked_request = (
        BloodRequest.objects
        .select_for_update()
        .select_related(
            "blood_bank",
            "blood_group",
            "component",
        )
        .get(pk=blood_request.pk)
    )

    allowed_statuses = {
        BloodRequest.Status.ACCEPTED,
        BloodRequest.Status.PARTIALLY_FULFILLED,
    }

    if locked_request.status not in allowed_statuses:
        raise ValidationError(
            "Inventory can only be reserved for an "
            "accepted or partially fulfilled request."
        )

    if locked_request.blood_bank is None:
        raise ValidationError(
            "A blood bank must be assigned before "
            "inventory can be reserved."
        )

    try:
        inventory = (
            BloodInventory.objects
            .select_for_update()
            .get(
                blood_bank=(
                    locked_request.blood_bank
                ),
                blood_group=(
                    locked_request.blood_group
                ),
                component=(
                    locked_request.component
                ),
            )
        )

    except BloodInventory.DoesNotExist as error:
        raise ValidationError(
            "No matching inventory record exists for "
            "this blood group and component."
        ) from error

    reservation = (
        BloodRequestReservation.objects
        .select_for_update()
        .filter(
            blood_request=locked_request
        )
        .first()
    )

    currently_reserved = (
        reservation.reserved_units
        if reservation
        else 0
    )

    remaining_required = (
        locked_request.units_required
        - locked_request.units_fulfilled
        - currently_reserved
    )

    if quantity > remaining_required:
        raise ValidationError(
            "Reservation exceeds the request's "
            "remaining required units."
        )

    available_units = (
        inventory.total_units
        - inventory.reserved_units
    )

    if quantity > available_units:
        raise ValidationError(
            (
                "Insufficient available inventory. "
                f"Only {available_units} unit(s) "
                "are available."
            )
        )

    if reservation is None:
        reservation = (
            BloodRequestReservation.objects.create(
                blood_request=locked_request,
                inventory=inventory,
                reserved_units=quantity,
                fulfilled_units=0,
                status=(
                    BloodRequestReservation
                    .Status.ACTIVE
                ),
                created_by=created_by,
            )
        )

    else:
        if reservation.inventory_id != inventory.id:
            raise ValidationError(
                "The existing reservation belongs to "
                "a different inventory record."
            )

        if reservation.status in {
            BloodRequestReservation.Status.FULFILLED,
            BloodRequestReservation.Status.RELEASED,
        }:
            raise ValidationError(
                "This reservation is already closed."
            )

        reservation.reserved_units += quantity

        if reservation.fulfilled_units > 0:
            reservation.status = (
                BloodRequestReservation
                .Status.PARTIALLY_FULFILLED
            )
        else:
            reservation.status = (
                BloodRequestReservation.Status.ACTIVE
            )

        reservation.save(
            update_fields=[
                "reserved_units",
                "status",
                "updated_at",
            ]
        )

    inventory.reserved_units += quantity
    inventory.last_updated_by = created_by

    inventory.save(
        update_fields=[
            "reserved_units",
            "last_updated_by",
            "last_updated_at",
        ]
    )

    notify_requester(
        blood_request=locked_request,
        notification_type=(
            Notification.Type.INVENTORY_RESERVED
        ),
        title="Blood units reserved",
        message=(
            f"{quantity} unit(s) were reserved for "
            f"request "
            f"{locked_request.request_number}."
        ),
    )

    return reservation


@transaction.atomic
def fulfil_inventory_reservation(
    *,
    blood_request,
    quantity,
    fulfilled_by,
    note="",
):
    """
    Issue reserved units and update request fulfilment.
    """

    _validate_authenticated_user(fulfilled_by)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "Fulfilment quantity must be a whole number."
        ) from error

    if quantity <= 0:
        raise ValidationError(
            "Fulfilment quantity must be greater than zero."
        )

    note = str(note).strip()

    if not note:
        raise ValidationError(
            "A fulfilment note is required."
        )

    locked_request = (
        BloodRequest.objects
        .select_for_update()
        .get(pk=blood_request.pk)
    )

    try:
        reservation = (
            BloodRequestReservation.objects
            .select_for_update()
            .select_related("inventory")
            .get(
                blood_request=locked_request
            )
        )

    except BloodRequestReservation.DoesNotExist as error:
        raise ValidationError(
            "No inventory reservation exists for "
            "this request."
        ) from error

    if reservation.status in {
        BloodRequestReservation.Status.FULFILLED,
        BloodRequestReservation.Status.RELEASED,
    }:
        raise ValidationError(
            "This reservation is already closed."
        )

    if quantity > reservation.reserved_units:
        raise ValidationError(
            "Fulfilment quantity exceeds the "
            "currently reserved units."
        )

    inventory = (
        BloodInventory.objects
        .select_for_update()
        .get(pk=reservation.inventory_id)
    )

    if quantity > inventory.reserved_units:
        raise ValidationError(
            "Inventory reserved quantity is inconsistent."
        )

    new_fulfilled_total = (
        locked_request.units_fulfilled
        + quantity
    )

    if new_fulfilled_total > (
        locked_request.units_required
    ):
        raise ValidationError(
            "Fulfilment exceeds the requested units."
        )

    # Release these units from the reserved count before
    # recording the physical stock issue.
    inventory.reserved_units -= quantity
    inventory.last_updated_by = fulfilled_by

    inventory.save(
        update_fields=[
            "reserved_units",
            "last_updated_by",
            "last_updated_at",
        ]
    )

    record_inventory_transaction(
        inventory=inventory,
        transaction_type=(
            InventoryTransaction.Type.ISSUED
        ),
        quantity=quantity,
        reason=note,
        created_by=fulfilled_by,
        reference_number=(
            locked_request.request_number
        ),
    )

    reservation.reserved_units -= quantity
    reservation.fulfilled_units += quantity

    if new_fulfilled_total == (
        locked_request.units_required
    ):
        reservation.status = (
            BloodRequestReservation.Status.FULFILLED
        )

        new_status = (
            BloodRequest.Status.COMPLETED
        )

    else:
        reservation.status = (
            BloodRequestReservation
            .Status.PARTIALLY_FULFILLED
        )

        new_status = (
            BloodRequest.Status.PARTIALLY_FULFILLED
        )

    reservation.save(
        update_fields=[
            "reserved_units",
            "fulfilled_units",
            "status",
            "updated_at",
        ]
    )

    updated_request = transition_blood_request(
        blood_request=locked_request,
        new_status=new_status,
        changed_by=fulfilled_by,
        note=note,
        units_fulfilled=new_fulfilled_total,
    )

    return updated_request, reservation


@transaction.atomic
def release_inventory_reservation(
    *,
    blood_request,
    released_by=None,
    reason,
    system_operation=False,
):
    """
    Return unfulfilled reserved units to availability.

    Total physical stock does not change.

    A normal release requires an authenticated user.
    System operations may release reservations without
    an authenticated user.
    """

    _validate_authenticated_user(
        released_by,
        system_operation=system_operation,
    )

    reason = str(reason).strip()

    if not reason:
        raise ValidationError(
            "A release reason is required."
        )

    locked_request = (
        BloodRequest.objects
        .select_for_update()
        .get(pk=blood_request.pk)
    )

    reservation = (
        BloodRequestReservation.objects
        .select_for_update()
        .select_related("inventory")
        .filter(
            blood_request=locked_request
        )
        .first()
    )

    if reservation is None:
        return None

    if reservation.status in {
        BloodRequestReservation.Status.RELEASED,
        BloodRequestReservation.Status.FULFILLED,
    }:
        return reservation

    inventory = (
        BloodInventory.objects
        .select_for_update()
        .get(pk=reservation.inventory_id)
    )

    if reservation.reserved_units > (
        inventory.reserved_units
    ):
        raise ValidationError(
            "Inventory reserved quantity is inconsistent."
        )

    inventory.reserved_units -= (
        reservation.reserved_units
    )

    inventory_update_fields = [
        "reserved_units",
        "last_updated_at",
    ]

    if released_by is not None:
        inventory.last_updated_by = released_by
        inventory_update_fields.append(
            "last_updated_by"
        )

    inventory.save(
        update_fields=inventory_update_fields
    )

    reservation.reserved_units = 0

    reservation.status = (
        BloodRequestReservation.Status.RELEASED
    )

    reservation.released_by = released_by
    reservation.release_reason = reason
    reservation.released_at = timezone.now()

    reservation.save(
        update_fields=[
            "reserved_units",
            "status",
            "released_by",
            "release_reason",
            "released_at",
            "updated_at",
        ]
    )

    return reservation