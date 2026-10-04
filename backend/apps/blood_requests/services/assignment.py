from django.core.exceptions import ValidationError
from django.db import transaction
from apps.blood_banks.models import BloodBank
from apps.blood_requests.models import (
    BloodRequest,
    BloodRequestBankAssignment,
    BloodRequestReservation,
)
from apps.notifications.models import Notification
from apps.notifications.services import (
    notify_assigned_bank,
    notify_requester,
)


@transaction.atomic
def assign_blood_bank(
    *,
    blood_request,
    blood_bank,
    assigned_by,
    reason="",
):
    """
    Assign or change the selected bank while the
    request is still pending.
    """

    if (
        not assigned_by
        or not assigned_by.is_authenticated
    ):
        raise ValidationError(
            "An authenticated user is required."
        )

    locked_request = (
        BloodRequest.objects
        .select_for_update()
        .select_related("blood_bank")
        .get(pk=blood_request.pk)
    )

    if locked_request.status != (
        BloodRequest.Status.PENDING
    ):
        raise ValidationError(
            "The blood bank can only be changed while "
            "the request is pending."
        )

    public_statuses = {
        BloodBank.VerificationStatus.VERIFIED,
        BloodBank.VerificationStatus
        .DIRECTORY_IMPORTED,
    }

    if not blood_bank.is_active:
        raise ValidationError(
            "The selected blood bank is inactive."
        )

    if not blood_bank.is_public:
        raise ValidationError(
            "The selected blood bank is not public."
        )

    if (
        blood_bank.verification_status
        not in public_statuses
    ):
        raise ValidationError(
            "The selected blood bank is not verified."
        )

    active_reservation_exists = (
        BloodRequestReservation.objects.filter(
            blood_request=locked_request,
            reserved_units__gt=0,
        ).exists()
    )

    if active_reservation_exists:
        raise ValidationError(
            "The bank cannot be changed while inventory "
            "is reserved."
        )

    previous_blood_bank = (
        locked_request.blood_bank
    )

    if (
        previous_blood_bank
        and previous_blood_bank.pk
        == blood_bank.pk
    ):
        raise ValidationError(
            "This blood bank is already assigned."
        )

    reason = str(reason).strip()

    if not reason:
        reason = (
            "Selected from nearby blood-bank "
            "suggestions."
        )

    locked_request.blood_bank = blood_bank

    locked_request.save(
        update_fields=[
            "blood_bank",
            "updated_at",
        ]
    )

    BloodRequestBankAssignment.objects.create(
        blood_request=locked_request,
        previous_blood_bank=previous_blood_bank,
        new_blood_bank=blood_bank,
        assigned_by=assigned_by,
        reason=reason,
    )

    notify_requester(
        blood_request=locked_request,
        notification_type=(
            Notification.Type.REQUEST_ASSIGNED
        ),
        title="Blood bank assigned",
        message=(
            f"{blood_bank.name} was assigned to "
            f"request "
            f"{locked_request.request_number}."
        ),
    )

    notify_assigned_bank(
        blood_request=locked_request,
        notification_type=(
            Notification.Type.REQUEST_ASSIGNED
        ),
        title="Blood request assigned",
        message=(
            f"Request "
            f"{locked_request.request_number} "
            f"has been assigned to your blood bank."
        ),
    )

    return locked_request