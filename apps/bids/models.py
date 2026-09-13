import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .choices import BidStatus


class BidProposal(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    proposal_number = models.CharField(max_length=50, unique=True)
    tender_request = models.ForeignKey(
        "tender.TenderRequest",
        on_delete=models.PROTECT,
        related_name="bid_proposals",
    )
    current_revision_number = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bid_proposals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bids_bid_proposal"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("tender_request", "-created_at"),
                name="bid_tender_created_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(current_revision_number__gt=0),
                name="bid_current_revision_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="bid_root_version_positive",
            ),
        ]

    def __str__(self):
        return self.proposal_number


class BidRevisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(
            "Revision Bid harus diubah melalui application service."
        )

    def delete(self):
        raise ValidationError("Revision Bid tidak dapat dihapus.")


class BidProposalRevision(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    bid_proposal = models.ForeignKey(
        BidProposal,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    tender_revision = models.ForeignKey(
        "tender.TenderRequestRevision",
        on_delete=models.PROTECT,
        related_name="bid_revisions",
    )
    selected_result = models.ForeignKey(
        "sourcing.ProcurementResult",
        on_delete=models.PROTECT,
        related_name="bid_revisions",
    )
    status = models.CharField(
        max_length=24,
        choices=BidStatus.choices,
        default=BidStatus.DRAFT,
    )
    target_margin_percent = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )
    total_purchase = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    total_bid_value = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    gross_profit = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    actual_margin_percent = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )
    max_margin_percent = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )
    is_hps_feasible = models.BooleanField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="IDR")
    calculation_version = models.CharField(max_length=32)
    snapshot_schema_version = models.PositiveIntegerField()
    selected_result_snapshot = models.JSONField()
    submission_snapshot = models.JSONField(null=True, blank=True)
    submission_hash = models.CharField(
        max_length=64, null=True, blank=True
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submitted_bid_revisions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bid_revisions",
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager.from_queryset(BidRevisionQuerySet)()

    class Meta:
        db_table = "bids_bid_proposal_revision"
        ordering = ("-revision_number",)
        indexes = [
            models.Index(
                fields=("status", "-updated_at"),
                name="bid_revision_status_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("bid_proposal", "revision_number"),
                name="bid_revision_number_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(revision_number__gt=0),
                name="bid_revision_number_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="bid_revision_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(snapshot_schema_version__gt=0),
                name="bid_revision_schema_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IDR"),
                name="bid_revision_currency_idr",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(target_margin_percent__isnull=True)
                    | (
                        models.Q(target_margin_percent__gte=0)
                        & models.Q(target_margin_percent__lt=100)
                    )
                ),
                name="bid_revision_margin_bounded",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(total_purchase__isnull=True)
                    | models.Q(total_purchase__gt=0)
                ),
                name="bid_revision_purchase_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(total_bid_value__isnull=True)
                    | models.Q(total_bid_value__gt=0)
                ),
                name="bid_revision_value_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(gross_profit__isnull=True)
                    | models.Q(gross_profit__gte=0)
                ),
                name="bid_revision_profit_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        target_margin_percent__isnull=True,
                        total_bid_value__isnull=True,
                        gross_profit__isnull=True,
                        actual_margin_percent__isnull=True,
                        max_margin_percent__isnull=True,
                        is_hps_feasible__isnull=True,
                    )
                    | models.Q(
                        target_margin_percent__isnull=False,
                        total_purchase__isnull=False,
                        total_bid_value__isnull=False,
                        gross_profit__isnull=False,
                        actual_margin_percent__isnull=False,
                    )
                ),
                name="bid_revision_pricing_payload_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=BidStatus.DRAFT,
                        submission_snapshot__isnull=True,
                        submission_hash__isnull=True,
                        submitted_by__isnull=True,
                        submitted_at__isnull=True,
                    )
                    | models.Q(
                        status__in=(
                            BidStatus.WAITING_APPROVAL,
                            BidStatus.APPROVED,
                            BidStatus.REJECTED,
                            BidStatus.SIGNED,
                            BidStatus.FINALIZED,
                        ),
                        target_margin_percent__isnull=False,
                        total_purchase__isnull=False,
                        total_bid_value__isnull=False,
                        gross_profit__isnull=False,
                        actual_margin_percent__isnull=False,
                        submission_snapshot__isnull=False,
                        submission_hash__isnull=False,
                        submitted_by__isnull=False,
                        submitted_at__isnull=False,
                    )
                ),
                name="bid_revision_submission_payload_valid",
            ),
        ]

    @property
    def is_priced(self):
        return self.target_margin_percent is not None

    MATERIAL_FIELDS = (
        "bid_proposal_id",
        "revision_number",
        "tender_revision_id",
        "selected_result_id",
        "target_margin_percent",
        "total_purchase",
        "total_bid_value",
        "gross_profit",
        "actual_margin_percent",
        "max_margin_percent",
        "is_hps_feasible",
        "currency",
        "calculation_version",
        "snapshot_schema_version",
        "selected_result_snapshot",
        "submission_snapshot",
        "submission_hash",
        "submitted_by_id",
        "submitted_at",
        "created_by_id",
    )

    ALLOWED_TRANSITIONS = {
        BidStatus.DRAFT: {BidStatus.DRAFT, BidStatus.WAITING_APPROVAL},
        BidStatus.WAITING_APPROVAL: {
            BidStatus.APPROVED,
            BidStatus.REJECTED,
        },
        BidStatus.APPROVED: {BidStatus.SIGNED},
        BidStatus.SIGNED: {BidStatus.FINALIZED},
    }

    def clean(self):
        super().clean()
        if (
            self.bid_proposal_id
            and self.tender_revision_id
            and self.bid_proposal.tender_request_id
            != self.tender_revision.tender_request_id
        ):
            raise ValidationError(
                "Revision tender tidak berasal dari Tender Bid."
            )
        if (
            self.selected_result_id
            and self.tender_revision_id
            and self.selected_result.tender_revision_id
            != self.tender_revision_id
        ):
            raise ValidationError(
                "Procurement Result tidak sesuai revision tender."
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            allowed = self.ALLOWED_TRANSITIONS.get(previous.status, set())
            if self.status not in allowed:
                raise ValidationError("Transition status Bid tidak valid.")
            if previous.status != BidStatus.DRAFT:
                changed = any(
                    getattr(previous, field) != getattr(self, field)
                    for field in self.MATERIAL_FIELDS
                )
                if changed:
                    raise ValidationError(
                        "Bid yang disubmit tidak dapat diubah."
                    )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Revision Bid tidak dapat dihapus.")

    def __str__(self):
        return (
            f"{self.bid_proposal.proposal_number} "
            f"R{self.revision_number}"
        )


class BidItemQuerySet(models.QuerySet):
    def _assert_draft(self):
        if self.exclude(bid_revision__status=BidStatus.DRAFT).exists():
            raise ValidationError(
                "Item Bid yang disubmit tidak dapat diubah."
            )

    def update(self, **kwargs):
        self._assert_draft()
        return super().update(**kwargs)

    def delete(self):
        self._assert_draft()
        return super().delete()


class BidProposalItem(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    bid_revision = models.ForeignKey(
        BidProposalRevision,
        on_delete=models.CASCADE,
        related_name="items",
    )
    tender_request_item = models.ForeignKey(
        "tender.TenderRequestItem",
        on_delete=models.PROTECT,
        related_name="bid_items",
    )
    line_number = models.PositiveIntegerField()
    product_snapshot = models.JSONField()
    requested_quantity = models.DecimalField(
        max_digits=18, decimal_places=3
    )
    unit = models.CharField(max_length=32)
    item_purchase_total = models.DecimalField(
        max_digits=20, decimal_places=2
    )
    unit_purchase_cost = models.DecimalField(
        max_digits=20, decimal_places=4
    )
    bid_unit_price = models.DecimalField(max_digits=20, decimal_places=4)
    item_bid_total = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3, default="IDR")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(BidItemQuerySet)()

    class Meta:
        db_table = "bids_bid_proposal_item"
        ordering = ("line_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("bid_revision", "tender_request_item"),
                name="bid_item_tender_unique",
            ),
            models.UniqueConstraint(
                fields=("bid_revision", "line_number"),
                name="bid_item_line_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(line_number__gt=0),
                name="bid_item_line_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_quantity__gt=0),
                name="bid_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(item_purchase_total__gt=0),
                name="bid_item_purchase_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_purchase_cost__gt=0),
                name="bid_item_unit_purchase_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(bid_unit_price__gt=0),
                name="bid_item_unit_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(item_bid_total__gt=0),
                name="bid_item_total_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IDR"),
                name="bid_item_currency_idr",
            ),
        ]

    def _assert_draft(self):
        status = BidProposalRevision.objects.filter(
            pk=self.bid_revision_id
        ).values_list("status", flat=True).get()
        if status != BidStatus.DRAFT:
            raise ValidationError(
                "Item Bid yang disubmit tidak dapat diubah."
            )

    def save(self, *args, **kwargs):
        self._assert_draft()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._assert_draft()
        return super().delete(*args, **kwargs)
