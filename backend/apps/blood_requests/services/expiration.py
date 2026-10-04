from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.blood_requests.models import (
    BloodRequest,
)
from apps.blood_requests.services.reservations import (
    release_inventory_reservation,
)
from apps.blood_requests.services.workflow import (
    transition_blood_request,
)


EXPIRABLE_STATUSES = {
    BloodRequest.Status.PENDING,
    BloodRequest.Status.UNDER_REVIEW,
    BloodRequest.Status.ACCEPTED,
    BloodRequest.Status.PARTIALLY_FULFILLED,
}


@transaction.atomic
def expire_single_request(
    *,
    blood_request,
):
    locked_request = (
        BloodRequest.objects
        .select_for_update()
        .get(pk=blood_request.pk)
    )

    if (
        locked_request.status
        not in EXPIRABLE_STATUSES
    ):
        return False

    release_inventory_reservation(
        blood_request=locked_request,
        released_by=None,
        reason="Request expired automatically.",
        system_operation=True,
    )

    expired_request = transition_blood_request(
        blood_request=locked_request,
        new_status=BloodRequest.Status.EXPIRED,
        changed_by=None,
        note="Request expired automatically.",
        system_operation=True,
    )

    return True


def expire_due_requests():
    now = timezone.now()
    today = timezone.localdate()

    due_requests = (
        BloodRequest.objects
        .filter(
            status__in=EXPIRABLE_STATUSES
        )
        .filter(
            Q(expires_at__lte=now)
            | Q(
                expires_at__isnull=True,
                required_date__lt=today,
            )
        )
        .only(
            "id",
            "status",
            "expires_at",
            "required_date",
        )
    )

    expired_count = 0

    for blood_request in due_requests.iterator():
        if expire_single_request(
            blood_request=blood_request
        ):
            expired_count += 1

    return expired_count