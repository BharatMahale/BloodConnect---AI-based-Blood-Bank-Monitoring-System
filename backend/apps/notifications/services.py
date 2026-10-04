from apps.notifications.models import (
    Notification,
)


def create_notification(
    *,
    recipient,
    notification_type,
    title,
    message,
    blood_request=None,
    data=None,
):
    """
    Create an in-app notification.

    The service intentionally does not expose private
    patient information in the notification message.
    """

    if recipient is None:
        return None

    return Notification.objects.create(
        recipient=recipient,
        blood_request=blood_request,
        notification_type=notification_type,
        title=str(title).strip(),
        message=str(message).strip(),
        data=data or {},
    )


def notify_requester(
    *,
    blood_request,
    notification_type,
    title,
    message,
):
    return create_notification(
        recipient=blood_request.requester,
        blood_request=blood_request,
        notification_type=notification_type,
        title=title,
        message=message,
        data={
            "request_id": str(
                blood_request.id
            ),
            "request_number": (
                blood_request.request_number
            ),
            "status": blood_request.status,
        },
    )


def notify_assigned_bank(
    *,
    blood_request,
    notification_type,
    title,
    message,
):
    blood_bank = blood_request.blood_bank

    if (
        blood_bank is None
        or blood_bank.owner is None
    ):
        return None

    return create_notification(
        recipient=blood_bank.owner,
        blood_request=blood_request,
        notification_type=notification_type,
        title=title,
        message=message,
        data={
            "request_id": str(
                blood_request.id
            ),
            "request_number": (
                blood_request.request_number
            ),
            "status": blood_request.status,
        },
    )