from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.blood_requests.models import (
    BloodRequest,
    BloodRequestStatusHistory,
)
from apps.notifications.models import Notification
from apps.notifications.services import (
    notify_assigned_bank,
    notify_requester,
)


ALLOWED_TRANSITIONS = {
    BloodRequest.Status.PENDING: {
        BloodRequest.Status.UNDER_REVIEW,
        BloodRequest.Status.CANCELLED,
        BloodRequest.Status.EXPIRED,
    },

    BloodRequest.Status.UNDER_REVIEW: {
        BloodRequest.Status.ACCEPTED,
        BloodRequest.Status.REJECTED,
        BloodRequest.Status.CANCELLED,
        BloodRequest.Status.EXPIRED,
    },

    BloodRequest.Status.ACCEPTED: {
        BloodRequest.Status.PARTIALLY_FULFILLED,
        BloodRequest.Status.COMPLETED,
        BloodRequest.Status.CANCELLED,
        BloodRequest.Status.EXPIRED,
    },

    BloodRequest.Status.PARTIALLY_FULFILLED: {
        BloodRequest.Status.COMPLETED,
        BloodRequest.Status.CANCELLED,
        BloodRequest.Status.EXPIRED,
    },

    BloodRequest.Status.REJECTED: set(),
    BloodRequest.Status.CANCELLED: set(),
    BloodRequest.Status.COMPLETED: set(),
    BloodRequest.Status.EXPIRED: set(),
}


REVIEW_STATUSES = {
    BloodRequest.Status.UNDER_REVIEW,
    BloodRequest.Status.ACCEPTED,
    BloodRequest.Status.PARTIALLY_FULFILLED,
    BloodRequest.Status.REJECTED,
    BloodRequest.Status.COMPLETED,
}


NOTE_REQUIRED_STATUSES = {
    BloodRequest.Status.REJECTED,
    BloodRequest.Status.CANCELLED,
}


@transaction.atomic
def create_blood_request(
    *,
    requester,
    request_data,
):
    """
    Create a blood request and its initial status record.

    Notifications are sent to the requester and the assigned
    blood bank, if a blood bank has already been assigned.
    """

    if (
        not requester
        or not requester.is_authenticated
    ):
        raise ValidationError(
            "An authenticated requester is required."
        )

    request_data = dict(request_data)

    required_date = request_data.get(
        "required_date"
    )

    if (
        required_date
        and not request_data.get("expires_at")
    ):
        expiry_datetime = datetime.combine(
            required_date,
            time.max,
        )

        request_data["expires_at"] = (
            timezone.make_aware(
                expiry_datetime,
                timezone.get_current_timezone(),
            )
        )

    blood_request = BloodRequest.objects.create(
        requester=requester,
        status=BloodRequest.Status.PENDING,
        units_fulfilled=0,
        **request_data,
    )

    BloodRequestStatusHistory.objects.create(
        blood_request=blood_request,
        previous_status="",
        new_status=BloodRequest.Status.PENDING,
        note="Blood request submitted.",
        changed_by=requester,
    )

    notify_requester(
        blood_request=blood_request,
        notification_type=(
            Notification.Type.REQUEST_SUBMITTED
        ),
        title="Blood request submitted",
        message=(
            f"Your request "
            f"{blood_request.request_number} "
            f"was submitted successfully."
        ),
    )

    notify_assigned_bank(
        blood_request=blood_request,
        notification_type=(
            Notification.Type.REQUEST_SUBMITTED
        ),
        title="New blood request received",
        message=(
            f"Blood request "
            f"{blood_request.request_number} "
            f"has been assigned to your blood bank."
        ),
    )

    return blood_request


@transaction.atomic
def transition_blood_request(
    *,
    blood_request,
    new_status,
    changed_by=None,
    note="",
    units_fulfilled=None,
    system_operation=False,
):
    """
    Change blood request status and create an
    audit-history record.

    Normal operations require an authenticated user.

    System operations are allowed without an authenticated
    user, but they may only change a request to EXPIRED.

    Notifications are generated after successful
    status transitions.
    """

    authenticated_actor = bool(
        changed_by
        and changed_by.is_authenticated
    )

    if (
        not authenticated_actor
        and not system_operation
    ):
        raise ValidationError(
            "An authenticated user is required."
        )

    if (
        system_operation
        and new_status
        != BloodRequest.Status.EXPIRED
    ):
        raise ValidationError(
            "System operations may only expire requests."
        )

    valid_statuses = {
        choice
        for choice, label
        in BloodRequest.Status.choices
    }

    if new_status not in valid_statuses:
        raise ValidationError(
            "Invalid blood-request status."
        )

    locked_request = (
        BloodRequest.objects
        .select_for_update()
        .select_related(
            "requester",
            "blood_bank",
            "blood_group",
            "component",
        )
        .get(pk=blood_request.pk)
    )

    previous_status = locked_request.status

    is_partial_progress = (
        previous_status
        == BloodRequest.Status.PARTIALLY_FULFILLED
        and new_status
        == BloodRequest.Status.PARTIALLY_FULFILLED
    )

    if (
        previous_status == new_status
        and not is_partial_progress
    ):
        raise ValidationError(
            "The request already has this status."
        )

    allowed_statuses = ALLOWED_TRANSITIONS.get(
        previous_status,
        set(),
    )

    if (
        new_status not in allowed_statuses
        and not is_partial_progress
    ):
        raise ValidationError(
            (
                "Cannot change request status from "
                f"{locked_request.get_status_display()} "
                f"to "
                f"{dict(BloodRequest.Status.choices)[new_status]}."
            )
        )

    note = str(note).strip()

    if (
        new_status in NOTE_REQUIRED_STATUSES
        and not note
    ):
        raise ValidationError(
            "A reason is required for this status change."
        )

    if new_status == (
        BloodRequest.Status.PARTIALLY_FULFILLED
    ):
        if units_fulfilled is None:
            raise ValidationError(
                "Fulfilled units are required for "
                "partial fulfilment."
            )

        try:
            units_fulfilled = int(
                units_fulfilled
            )

        except (TypeError, ValueError) as error:
            raise ValidationError(
                "Fulfilled units must be a whole number."
            ) from error

        if units_fulfilled <= 0:
            raise ValidationError(
                "Fulfilled units must be greater than zero."
            )

        if units_fulfilled >= (
            locked_request.units_required
        ):
            raise ValidationError(
                "Partial fulfilment must be less than "
                "the required units."
            )

        if units_fulfilled <= (
            locked_request.units_fulfilled
        ):
            raise ValidationError(
                "Fulfilled units must be greater than "
                "the current fulfilled quantity."
            )

        locked_request.units_fulfilled = (
            units_fulfilled
        )

    elif new_status == (
        BloodRequest.Status.COMPLETED
    ):
        locked_request.units_fulfilled = (
            locked_request.units_required
        )

    elif units_fulfilled is not None:
        raise ValidationError(
            "Fulfilled units can only be supplied for "
            "partial fulfilment or completion."
        )

    locked_request.status = new_status

    if new_status in REVIEW_STATUSES:
        if authenticated_actor:
            locked_request.reviewed_by = (
                changed_by
            )

        locked_request.reviewed_at = (
            timezone.now()
        )

        if note:
            locked_request.blood_bank_response = (
                note
            )

    locked_request.save(
        update_fields=[
            "status",
            "units_fulfilled",
            "reviewed_by",
            "reviewed_at",
            "blood_bank_response",
            "updated_at",
        ]
    )

    BloodRequestStatusHistory.objects.create(
        blood_request=locked_request,
        previous_status=previous_status,
        new_status=new_status,
        note=note,
        changed_by=(
            changed_by
            if authenticated_actor
            else None
        ),
    )

    notification_mapping = {
        BloodRequest.Status.UNDER_REVIEW: (
            Notification.Type.STATUS_UPDATED,
            "Blood request under review",
        ),
        BloodRequest.Status.ACCEPTED: (
            Notification.Type.STATUS_UPDATED,
            "Blood request accepted",
        ),
        BloodRequest.Status.PARTIALLY_FULFILLED: (
            Notification.Type.PARTIALLY_FULFILLED,
            "Blood request partially fulfilled",
        ),
        BloodRequest.Status.COMPLETED: (
            Notification.Type.REQUEST_COMPLETED,
            "Blood request completed",
        ),
        BloodRequest.Status.CANCELLED: (
            Notification.Type.REQUEST_CANCELLED,
            "Blood request cancelled",
        ),
        BloodRequest.Status.REJECTED: (
            Notification.Type.REQUEST_REJECTED,
            "Blood request rejected",
        ),
        BloodRequest.Status.EXPIRED: (
            Notification.Type.REQUEST_EXPIRED,
            "Blood request expired",
        ),
    }

    notification_details = (
        notification_mapping.get(new_status)
    )

    if notification_details:
        (
            notification_type,
            notification_title,
        ) = notification_details

        notify_requester(
            blood_request=locked_request,
            notification_type=notification_type,
            title=notification_title,
            message=(
                f"Request "
                f"{locked_request.request_number} "
                f"is now "
                f"{locked_request.get_status_display()}."
            ),
        )

    if new_status in {
        BloodRequest.Status.CANCELLED,
        BloodRequest.Status.EXPIRED,
    }:
        notify_assigned_bank(
            blood_request=locked_request,
            notification_type=(
                Notification.Type.STATUS_UPDATED
            ),
            title="Blood request closed",
            message=(
                f"Request "
                f"{locked_request.request_number} "
                f"is now "
                f"{locked_request.get_status_display()}."
            ),
        )

    return locked_request