from rest_framework import serializers
from apps.notifications.models import (
    Notification,
)


class NotificationSerializer(
    serializers.ModelSerializer
):
    notification_type_display = (
        serializers.CharField(
            source="get_notification_type_display",
            read_only=True,
        )
    )

    request_number = serializers.CharField(
        source="blood_request.request_number",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Notification

        fields = [
            "id",
            "notification_type",
            "notification_type_display",
            "title",
            "message",
            "blood_request",
            "request_number",
            "data",
            "is_read",
            "read_at",
            "created_at",
        ]

        read_only_fields = fields