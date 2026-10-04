from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
)
from apps.accounts.permissions import is_application_admin


class IsBloodBankOwnerOrAdminOrReadOnly(
    BasePermission
):
    """
    Public users can read visible blood-bank records.

    Only the owner or an administrator can update them.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return bool(
            request.user
            and request.user.is_authenticated
        )

    def has_object_permission(
        self,
        request,
        view,
        blood_bank,
    ):
        if request.method in SAFE_METHODS:
            return True

        user = request.user

        return (
            is_application_admin(user)
            or blood_bank.owner_id == user.id
        )
