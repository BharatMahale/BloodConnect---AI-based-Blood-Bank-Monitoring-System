from django.contrib import admin
from apps.notifications.models import (
    Notification,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "recipient",
        "notification_type",
        "title",
        "blood_request",
        "is_read",
        "created_at",
    ]

    list_filter = [
        "notification_type",
        "is_read",
        "created_at",
    ]

    search_fields = [
        "recipient__email",
        "title",
        "message",
        "blood_request__request_number",
    ]

    readonly_fields = [
        "id",
        "recipient",
        "blood_request",
        "notification_type",
        "title",
        "message",
        "data",
        "created_at",
    ]