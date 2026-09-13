from django.db import transaction
from django.utils import timezone

from apps.accounts.policies import require_active_user

from .models import Notification


def create_notification(
    *,
    recipient,
    notification_type,
    source_event_id,
    source_entity_type,
    source_entity_id,
    title,
    message,
):
    return Notification.objects.get_or_create(
        recipient=recipient,
        source_event_id=source_event_id,
        type=notification_type,
        defaults={
            "source_entity_type": source_entity_type,
            "source_entity_id": source_entity_id,
            "title": title,
            "message": message,
        },
    )[0]


def mark_notification_read(*, actor, notification_id):
    require_active_user(actor)
    with transaction.atomic():
        notification = Notification.objects.select_for_update().get(
            pk=notification_id,
            recipient=actor,
        )
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return notification
