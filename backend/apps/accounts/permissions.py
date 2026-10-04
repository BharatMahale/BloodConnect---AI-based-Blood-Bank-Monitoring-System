from rest_framework.permissions import BasePermission
from .models import Role


def is_application_admin(user):
    """Return whether a user has global BloodConnect authority."""

    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.user_roles.filter(
                role__code=Role.Code.ADMIN,
                role__is_active=True,
                is_active=True,
            ).exists()
        )
    )


class HasRole(BasePermission):
    """Base permission for checking an active user role."""

    required_roles = ()

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        return user.user_roles.filter(
            role__code__in=self.required_roles,
            role__is_active=True,
            is_active=True,
        ).exists()


class IsAdmin(HasRole):
    required_roles = (Role.Code.ADMIN,)

    def has_permission(self, request, view):
        return is_application_admin(request.user)


class IsBloodBankStaff(HasRole):
    required_roles = (Role.Code.BLOOD_BANK_STAFF,)


class IsDonor(HasRole):
    required_roles = (Role.Code.DONOR,)


class IsBloodSeeker(HasRole):
    required_roles = (Role.Code.SEEKER,)


class IsCampOrganizer(HasRole):
    required_roles = (Role.Code.CAMP_ORGANIZER,)


class IsAdminOrBloodBankStaff(HasRole):
    required_roles = (
        Role.Code.ADMIN,
        Role.Code.BLOOD_BANK_STAFF,
    )
