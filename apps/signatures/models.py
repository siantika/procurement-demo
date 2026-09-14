import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ImmutableSignatureQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Signature tidak dapat diubah.")

    def delete(self):
        raise ValidationError("Signature tidak dapat dihapus.")


class Signature(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    bid_revision = models.OneToOneField(
        "bids.BidProposalRevision",
        on_delete=models.PROTECT,
        related_name="signature",
    )
    approval_decision = models.OneToOneField(
        "approval.ApprovalDecision",
        on_delete=models.PROTECT,
        related_name="signature",
    )
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="signatures",
    )
    signer_name = models.CharField(max_length=255)
    signed_snapshot_hash = models.CharField(max_length=64)
    image_object_key = models.CharField(
        max_length=512, null=True, blank=True, unique=True
    )
    image_version_id = models.CharField(
        max_length=255, null=True, blank=True
    )
    image_mime_type = models.CharField(
        max_length=100, null=True, blank=True
    )
    image_size_bytes = models.PositiveBigIntegerField(
        null=True, blank=True
    )
    image_sha256 = models.CharField(
        max_length=64, null=True, blank=True
    )
    signed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableSignatureQuerySet)()

    class Meta:
        db_table = "signatures_signature"
        ordering = ("-signed_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        image_object_key__isnull=True,
                        image_version_id__isnull=True,
                        image_mime_type__isnull=True,
                        image_size_bytes__isnull=True,
                        image_sha256__isnull=True,
                    )
                    | models.Q(
                        image_object_key__isnull=False,
                        image_mime_type__in=("image/png", "image/jpeg"),
                        image_size_bytes__gt=0,
                        image_size_bytes__lte=1_048_576,
                        image_sha256__isnull=False,
                    )
                ),
                name="signature_image_metadata_valid",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.approval_decision_id
            and self.bid_revision_id
            and self.approval_decision.bid_revision_id
            != self.bid_revision_id
        ):
            raise ValidationError(
                "Approval tidak berasal dari Bid revision ini."
            )
        if (
            self.approval_decision_id
            and self.signed_by_id
            and self.approval_decision.decided_by_id
            != self.signed_by_id
        ):
            raise ValidationError(
                "Penandatangan harus sama dengan approving Manager."
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Signature tidak dapat diubah.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Signature tidak dapat dihapus.")
