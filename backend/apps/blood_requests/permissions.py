from rest_framework.permissions import (
    BasePermission,
)
from apps.accounts.permissions import is_application_admin


def manages_request_blood_bank(user, blood_request,):
    if is_application_admin(user):
        return True

    blood_bank = blood_request.blood_bank

    return bool(
        blood_bank
        and blood_bank.owner_id == user.id
    )


class IsBloodRequestParticipant(BasePermission):
    message = (
        "You do not have permission to access "
        "this blood request."
    )

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
        )

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ):
        user = request.user

        if is_application_admin(user):
            return True

        if obj.requester_id == user.id:
            return True

        return bool(
            obj.blood_bank
            and obj.blood_bank.owner_id == user.id
        )
