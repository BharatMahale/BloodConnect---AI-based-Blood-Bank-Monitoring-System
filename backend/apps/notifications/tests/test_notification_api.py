from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from apps.notifications.models import Notification


User = get_user_model()


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="requester@example.com",
            password="Requester@12345",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="OtherUser@12345",
        )

        self.user_notification = Notification.objects.create(
            recipient=self.user,
            notification_type="STATUS_UPDATED",
            title="Request status updated",
            message="Your blood request is now under review.",
        )

        self.other_notification = Notification.objects.create(
            recipient=self.other_user,
            notification_type="REQUEST_ASSIGNED",
            title="Request assigned",
            message="A request has been assigned to your blood bank.",
        )

    def test_anonymous_user_cannot_list_notifications(self):
        response = self.client.get(
            "/api/v1/notifications/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_can_only_list_own_notifications(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/v1/notifications/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        notifications = response.data.get(
            "results",
            response.data,
        )

        returned_ids = {
            str(notification["id"])
            for notification in notifications
        }

        self.assertIn(
            str(self.user_notification.id),
            returned_ids,
        )
        self.assertNotIn(
            str(self.other_notification.id),
            returned_ids,
        )

    def test_user_cannot_retrieve_another_users_notification(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            (
                f"/api/v1/notifications/"
                f"{self.other_notification.id}/"
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_user_can_mark_notification_as_read(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            (
                f"/api/v1/notifications/"
                f"{self.user_notification.id}/mark-read/"
            ),
            data={},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.user_notification.refresh_from_db()

        self.assertTrue(
            self.user_notification.is_read
        )
        self.assertIsNotNone(
            self.user_notification.read_at
        )

    def test_user_cannot_mark_another_users_notification_as_read(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            (
                f"/api/v1/notifications/"
                f"{self.other_notification.id}/mark-read/"
            ),
            data={},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.other_notification.refresh_from_db()

        self.assertFalse(
            self.other_notification.is_read
        )

    def test_mark_all_read_only_updates_authenticated_users_notifications(
        self,
    ):
        Notification.objects.create(
            recipient=self.user,
            notification_type="INVENTORY_RESERVED",
            title="Inventory reserved",
            message="Blood inventory has been reserved.",
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/notifications/mark-all-read/",
            data={},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.user,
                is_read=False,
            ).count(),
            0,
        )

        self.other_notification.refresh_from_db()

        self.assertFalse(
            self.other_notification.is_read
        )

    def test_unread_count_returns_only_users_unread_notifications(self):
        Notification.objects.create(
            recipient=self.user,
            notification_type="REQUEST_SUBMITTED",
            title="Request submitted",
            message="Your emergency request was submitted.",
        )

        Notification.objects.create(
            recipient=self.user,
            notification_type="REQUEST_COMPLETED",
            title="Request completed",
            message="Your request was completed.",
            is_read=True,
            read_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/v1/notifications/unread-count/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["unread_count"],
            2,
        )

    def test_notifications_can_be_filtered_by_read_status(self):
        Notification.objects.create(
            recipient=self.user,
            notification_type="REQUEST_COMPLETED",
            title="Request completed",
            message="Your request was completed.",
            is_read=True,
            read_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/v1/notifications/?is_read=false",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        notifications = response.data.get(
            "results",
            response.data,
        )

        self.assertEqual(
            len(notifications),
            1,
        )
        self.assertFalse(
            notifications[0]["is_read"]
        )