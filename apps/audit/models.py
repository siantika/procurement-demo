"""Model audit yang menyimpan fakta mutation secara append-only."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AuditEventQuerySet(models.QuerySet):
    """Tolak mutation massal yang melewati method model."""

    def update(self, **kwargs):
        raise ValidationError("AuditEvent tidak dapat diubah.")

    def delete(self):
        raise ValidationError("AuditEvent tidak dapat dihapus.")


class AuditEvent(models.Model):
    """Catatan immutable untuk satu perubahan state."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor_name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=64)
    entity_id = models.UUIDField()
    entity_revision = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=64)
    from_status = models.CharField(max_length=32, null=True, blank=True)
    to_status = models.CharField(max_length=32, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    correlation_id = models.CharField(max_length=100)
    occurred_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(AuditEventQuerySet)()

    class Meta:
        db_table = "audit_audit_event"
        ordering = ("-occurred_at", "-id")
        indexes = [
            models.Index(
                fields=("entity_type", "entity_id", "-occurred_at"),
                name="audit_entity_timeline_idx",
            ),
            models.Index(
                fields=("actor", "-occurred_at"),
                name="audit_actor_timeline_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(entity_revision__isnull=True)
                    | models.Q(entity_revision__gt=0)
                ),
                name="audit_event_revision_positive",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("AuditEvent tidak dapat diubah.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("AuditEvent tidak dapat dihapus.")
