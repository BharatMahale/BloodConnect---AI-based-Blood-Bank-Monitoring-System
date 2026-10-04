import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class Type(models.TextChoices):
        REQUEST_SUBMITTED = (
            "REQUEST_SUBMITTED",
            "Request Submitted",
        )
        REQUEST_ASSIGNED = (
            "REQUEST_ASSIGNED",
            "Request Assigned",
        )
        STATUS_UPDATED = (
            "STATUS_UPDATED",
            "Status Updated",
        )
        INVENTORY_RESERVED = (
            "INVENTORY_RESERVED",
            "Inventory Reserved",
        )
        PARTIALLY_FULFILLED = (
            "PARTIALLY_FULFILLED",
            "Partially Fulfilled",
        )
        REQUEST_COMPLETED = (
            "REQUEST_COMPLETED",
            "Request Completed",
        )
        REQUEST_CANCELLED = (
            "REQUEST_CANCELLED",
            "Request Cancelled",
        )
        REQUEST_REJECTED = (
            "REQUEST_REJECTED",
            "Request Rejected",
        )
        REQUEST_EXPIRED = (
            "REQUEST_EXPIRED",
            "Request Expired",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    blood_request = models.ForeignKey(
        "blood_requests.BloodRequest",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    notification_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        db_index=True,
    )

    title = models.CharField(
        max_length=200
    )

    message = models.TextField()

    data = models.JSONField(
        default=dict,
        blank=True,
    )

    is_read = models.BooleanField(
        default=False,
        db_index=True,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "recipient",
                    "is_read",
                    "created_at",
                ],
                name="notification_user_read_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.recipient}: {self.title}"
        )

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()

            self.save(
                update_fields=[
                    "is_read",
                    "read_at",
                ]
            )