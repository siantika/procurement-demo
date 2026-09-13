from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.choices import UserRole
from apps.audit.models import AuditEvent

from .choices import NotificationType
from .models import Notification
from .services import create_notification

User = get_user_model()


class NotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.recipient = User.objects.create_user(
            username="notification-recipient",
            email="notification@example.test",
            password="StrongPassword123!",
            full_name="Notification Recipient",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.other = User.objects.create_user(
            username="notification-other",
            email="notification-other@example.test",
            password="StrongPassword123!",
            full_name="Notification Other",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.event = AuditEvent.objects.create(
            actor=cls.recipient,
            actor_name=cls.recipient.full_name,
            entity_type="OptimizationRun",
            entity_id=cls.recipient.pk,
            action="OPTIMIZATION_COMPLETED",
            correlation_id="notification-test",
        )

    def notification(self):
        return create_notification(
            recipient=self.recipient,
            notification_type=NotificationType.OPTIMIZATION_COMPLETED,
            source_event_id=self.event.pk,
            source_entity_type="OptimizationRun",
            source_entity_id=self.recipient.pk,
            title="Optimization selesai",
            message="Satu rekomendasi tersedia.",
        )

    def test_creation_is_idempotent(self):
        first = self.notification()
        second = self.notification()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.count(), 1)

    def test_only_recipient_can_mark_notification_read(self):
        notification = self.notification()
        self.client.force_login(self.other)

        response = self.client.post(
            reverse(
                "notifications:mark-read",
                kwargs={"notification_id": notification.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_recipient_can_mark_notification_read(self):
        notification = self.notification()
        self.client.force_login(self.recipient)

        response = self.client.post(
            reverse(
                "notifications:mark-read",
                kwargs={"notification_id": notification.pk},
            )
        )

        self.assertRedirects(response, reverse("notifications:list"))
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
