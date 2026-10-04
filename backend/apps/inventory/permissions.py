from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
)
from apps.accounts.permissions import is_application_admin


class IsBloodBankOwnerOrAdmin(BasePermission):
    """
    Public users can view public inventory.

    Inventory creation, stock updates and transaction
    history are restricted to the blood-bank owner
    or an administrator.
    """

    message = (
        "You do not have permission to manage "
        "this blood bank's inventory."
    )

    public_actions = [
        "list",
        "retrieve",
    ]

    def has_permission(self, request, view):
        action = getattr(view, "action", None)

        if (
            request.method in SAFE_METHODS
            and action in self.public_actions
        ):
            return True

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
        action = getattr(view, "action", None)

        if (
            request.method in SAFE_METHODS
            and action in self.public_actions
        ):
            return True

        if not request.user.is_authenticated:
            return False

        if is_application_admin(request.user):
            return True

        blood_bank = getattr(
            obj,
            "blood_bank",
            None,
        )

        return bool(
            blood_bank
            and blood_bank.owner_id
            == request.user.id
        )


def can_manage_blood_bank(user, blood_bank):
    if not user or not user.is_authenticated:
        return False

    if is_application_admin(user):
        return True

    return blood_bank.owner_id == user.id
