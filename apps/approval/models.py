import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .choices import ApprovalDecisionType


class ImmutableDecisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Approval Decision tidak dapat diubah.")

    def delete(self):
        raise ValidationError("Approval Decision tidak dapat dihapus.")


class ApprovalDecision(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    bid_revision = models.OneToOneField(
        "bids.BidProposalRevision",
        on_delete=models.PROTECT,
        related_name="approval_decision",
    )
    decision = models.CharField(
        max_length=16, choices=ApprovalDecisionType.choices
    )
    reason = models.TextField(null=True, blank=True)
    submission_hash = models.CharField(max_length=64)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_decisions",
    )
    decided_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableDecisionQuerySet)()

    class Meta:
        db_table = "approval_approval_decision"
        ordering = ("-decided_at", "-id")
        indexes = [
            models.Index(
                fields=("decided_by", "-decided_at"),
                name="approval_manager_decided_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        decision=ApprovalDecisionType.APPROVED,
                        reason__isnull=True,
                    )
                    | models.Q(
                        decision=ApprovalDecisionType.REJECTED,
                        reason__isnull=False,
                    )
                    & ~models.Q(reason="")
                ),
                name="approval_decision_reason_valid",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Approval Decision tidak dapat diubah.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Approval Decision tidak dapat dihapus.")
