import uuid

from django.conf import settings
from django.db import models

from .choices import NotificationType


class Notification(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    type = models.CharField(
        max_length=40, choices=NotificationType.choices
    )
    source_event_id = models.UUIDField()
    source_entity_type = models.CharField(max_length=64)
    source_entity_id = models.UUIDField()
    title = models.CharField(max_length=255)
    message = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("recipient", "read_at", "-created_at"),
                name="notif_recipient_read_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("recipient", "source_event_id", "type"),
                name="notification_event_recipient_unique",
            )
        ]

    @property
    def is_read(self):
        return self.read_at is not None
