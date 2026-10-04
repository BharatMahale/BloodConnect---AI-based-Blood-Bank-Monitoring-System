from django.utils import timezone
from django_filters.rest_framework import (
    DjangoFilterBackend,
)
from drf_spectacular.utils import extend_schema
from rest_framework import (
    filters,
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from apps.notifications.models import (
    Notification,
)
from apps.notifications.serializers import (
    NotificationSerializer,
)


class NotificationViewSet(
    viewsets.ReadOnlyModelViewSet
):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]

    filterset_fields = [
        "is_read",
        "notification_type",
    ]

    ordering_fields = [
        "created_at",
        "is_read",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()

        return (
            Notification.objects
            .filter(
                recipient=self.request.user
            )
            .select_related(
                "blood_request"
            )
        )

    @extend_schema(
        summary="Mark a notification as read",
        responses=NotificationSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="mark-read",
    )
    def mark_read(self, request, pk=None):
        notification = self.get_object()

        notification.mark_as_read()

        serializer = NotificationSerializer(
            notification
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Mark all notifications as read",
        responses={
            status.HTTP_200_OK: dict
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="mark-all-read",
    )
    def mark_all_read(self, request):
        now = timezone.now()

        updated_count = (
            self.get_queryset()
            .filter(is_read=False)
            .update(
                is_read=True,
                read_at=now,
            )
        )

        return Response(
            {
                "message": (
                    "All notifications marked as read."
                ),
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Get unread notification count",
        responses={
            status.HTTP_200_OK: dict
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="unread-count",
    )
    def unread_count(self, request):
        count = (
            self.get_queryset()
            .filter(is_read=False)
            .count()
        )

        return Response(
            {
                "unread_count": count
            },
            status=status.HTTP_200_OK,
        )
