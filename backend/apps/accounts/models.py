import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from .managers import UserManager


class User(AbstractUser):
    """Application user authenticated through email."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    username = None
    email = models.EmailField(
        unique=True,
        db_index=True,
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
    )
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    def has_role(self, role_code):
        """Return whether the user has the requested active role."""

        if self.is_superuser:
            return True

        return self.user_roles.filter(
            role__code=role_code,
            is_active=True,
        ).exists()


class Role(models.Model):
    """Role available to a BloodConnect user."""

    class Code(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        BLOOD_BANK_STAFF = (
            "BLOOD_BANK_STAFF",
            "Blood Bank Staff",
        )
        DONOR = "DONOR", "Blood Donor"
        SEEKER = "SEEKER", "Blood Seeker"
        CAMP_ORGANIZER = (
            "CAMP_ORGANIZER",
            "Camp Organizer",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(
        max_length=30,
        choices=Code.choices,
        unique=True,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """Role assigned to a user."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="user_roles",
    )
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_user_roles",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                name="unique_user_role",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_primary=True),
                name="one_primary_role_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.role.code}"