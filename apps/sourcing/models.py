"""Supplier Offer sebagai data komersial versioned."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .choices import ResultSourceType, ResultStatus


class SupplierOffer(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    supplier = models.ForeignKey(
        "catalog.Supplier",
        on_delete=models.PROTECT,
        related_name="offers",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="offers",
    )
    supersedes_offer = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="superseding_offer",
    )
    supplier_reference = models.CharField(max_length=100, blank=True)
    base_unit_price = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    discount_percent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    net_purchase_price = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="IDR")
    available_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=3,
        null=True,
        blank=True,
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    calculation_version = models.CharField(max_length=32)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_supplier_offers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sourcing_supplier_offer"
        ordering = (
            "product__name",
            "net_purchase_price",
            "supplier__code",
        )
        indexes = [
            models.Index(fields=("product", "is_active", "valid_until")),
            models.Index(fields=("supplier", "product", "created_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(base_unit_price__gt=0),
                name="sourcing_offer_base_price_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_percent__gte=0)
                    & models.Q(discount_percent__lte=100)
                ),
                name="sourcing_offer_discount_bounded",
            ),
            models.CheckConstraint(
                condition=models.Q(net_purchase_price__gte=0),
                name="sourcing_offer_net_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(available_quantity__isnull=True)
                    | models.Q(available_quantity__gt=0)
                ),
                name="sourcing_offer_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IDR"),
                name="sourcing_offer_currency_idr",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(valid_from__isnull=True)
                    | models.Q(valid_until__isnull=True)
                    | models.Q(valid_until__gte=models.F("valid_from"))
                ),
                name="sourcing_offer_valid_date_order",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="sourcing_offer_version_positive",
            ),
        ]

    def __str__(self):
        return f"{self.supplier.code} / {self.product.code}"


class ProcurementResultQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.filter(status=ResultStatus.VALID).exists():
            raise ValidationError(
                "Procurement Result VALID tidak dapat diubah."
            )
        return super().update(**kwargs)

    def delete(self):
        raise ValidationError("Procurement Result tidak dapat dihapus.")


class ProcurementResult(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    tender_revision = models.ForeignKey(
        "tender.TenderRequestRevision",
        on_delete=models.PROTECT,
        related_name="procurement_results",
    )
    source_type = models.CharField(
        max_length=20, choices=ResultSourceType.choices
    )
    status = models.CharField(
        max_length=20,
        choices=ResultStatus.choices,
        default=ResultStatus.DRAFT,
    )
    # M3 mengubah logical UUID ini menjadi FK setelah OptimizationRun ada.
    optimization_run_id = models.UUIDField(null=True, blank=True)
    source_result = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customized_results",
    )
    rank = models.PositiveIntegerField(null=True, blank=True)
    total_purchase = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="IDR")
    calculation_version = models.CharField(max_length=32)
    snapshot_schema_version = models.PositiveIntegerField(
        null=True, blank=True
    )
    result_snapshot = models.JSONField(null=True, blank=True)
    result_hash = models.CharField(
        max_length=64, null=True, blank=True
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_procurement_results",
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager.from_queryset(ProcurementResultQuerySet)()

    class Meta:
        db_table = "sourcing_procurement_result"
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(
                fields=("tender_revision", "status", "total_purchase"),
                name="src_result_tender_status_idx",
            ),
            models.Index(
                fields=("optimization_run_id", "rank"),
                name="src_result_run_rank_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="sourcing_result_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IDR"),
                name="sourcing_result_currency_idr",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(rank__isnull=True)
                    | models.Q(rank__gt=0)
                ),
                name="sourcing_result_rank_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(total_purchase__isnull=True)
                    | models.Q(total_purchase__gt=0)
                ),
                name="sourcing_result_total_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(snapshot_schema_version__isnull=True)
                    | models.Q(snapshot_schema_version__gt=0)
                ),
                name="sourcing_result_schema_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        source_type=ResultSourceType.MANUAL,
                        optimization_run_id__isnull=True,
                        source_result__isnull=True,
                        rank__isnull=True,
                    )
                    | models.Q(
                        source_type=ResultSourceType.CUSTOMIZED,
                        optimization_run_id__isnull=True,
                        source_result__isnull=False,
                        rank__isnull=True,
                    )
                    | models.Q(
                        source_type=ResultSourceType.OPTIMIZER,
                        optimization_run_id__isnull=False,
                        source_result__isnull=True,
                        rank__isnull=False,
                    )
                ),
                name="sourcing_result_source_lineage_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(source_result__isnull=True)
                    | ~models.Q(source_result=models.F("id"))
                ),
                name="sourcing_result_source_not_self",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=ResultStatus.DRAFT,
                        total_purchase__isnull=True,
                        snapshot_schema_version__isnull=True,
                        result_snapshot__isnull=True,
                        result_hash__isnull=True,
                        validated_at__isnull=True,
                    )
                    | models.Q(
                        status=ResultStatus.VALID,
                        total_purchase__isnull=False,
                        snapshot_schema_version__isnull=False,
                        result_snapshot__isnull=False,
                        result_hash__isnull=False,
                        validated_at__isnull=False,
                    )
                ),
                name="sourcing_result_state_payload_valid",
            ),
            models.UniqueConstraint(
                fields=("optimization_run_id", "rank"),
                condition=models.Q(optimization_run_id__isnull=False),
                name="sourcing_result_run_rank_unique",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous_status = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .get()
            )
            if previous_status == ResultStatus.VALID:
                raise ValidationError(
                    "Procurement Result VALID tidak dapat diubah."
                )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Procurement Result tidak dapat dihapus.")

    def __str__(self):
        return f"{self.tender_revision} / {self.get_source_type_display()}"


class ResultItemQuerySet(models.QuerySet):
    def _assert_draft(self):
        if self.filter(
            procurement_result__status=ResultStatus.VALID
        ).exists():
            raise ValidationError("Item Result VALID tidak dapat diubah.")

    def update(self, **kwargs):
        self._assert_draft()
        return super().update(**kwargs)

    def delete(self):
        self._assert_draft()
        return super().delete()


class ProcurementResultItem(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    procurement_result = models.ForeignKey(
        ProcurementResult,
        on_delete=models.CASCADE,
        related_name="items",
    )
    tender_request_item = models.ForeignKey(
        "tender.TenderRequestItem",
        on_delete=models.PROTECT,
        related_name="procurement_result_items",
    )
    line_number = models.PositiveIntegerField()
    requested_quantity_snapshot = models.DecimalField(
        max_digits=18, decimal_places=3
    )
    unit_snapshot = models.CharField(max_length=32)
    item_purchase_total = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="IDR")
    product_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager.from_queryset(ResultItemQuerySet)()

    class Meta:
        db_table = "sourcing_procurement_result_item"
        ordering = ("line_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("procurement_result", "tender_request_item"),
                name="sourcing_result_item_tender_unique",
            ),
            models.UniqueConstraint(
                fields=("procurement_result", "line_number"),
                name="sourcing_result_item_line_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(line_number__gt=0),
                name="sourcing_result_item_line_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_quantity_snapshot__gt=0),
                name="sourcing_result_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(item_purchase_total__isnull=True)
                    | models.Q(item_purchase_total__gt=0)
                ),
                name="sourcing_result_item_total_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IDR"),
                name="sourcing_result_item_currency_idr",
            ),
        ]

    def _assert_draft(self):
        status = ProcurementResult.objects.filter(
            pk=self.procurement_result_id
        ).values_list("status", flat=True).get()
        if status == ResultStatus.VALID:
            raise ValidationError("Item Result VALID tidak dapat diubah.")

    def save(self, *args, **kwargs):
        self._assert_draft()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._assert_draft()
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.procurement_result_id} / {self.line_number}"


class AllocationQuerySet(models.QuerySet):
    def _assert_draft(self):
        if self.filter(
            procurement_result_item__procurement_result__status=(
                ResultStatus.VALID
            )
        ).exists():
            raise ValidationError(
                "Allocation Result VALID tidak dapat diubah."
            )

    def update(self, **kwargs):
        self._assert_draft()
        return super().update(**kwargs)

    def delete(self):
        self._assert_draft()
        return super().delete()


class SupplierAllocation(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    procurement_result_item = models.ForeignKey(
        ProcurementResultItem,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    supplier_offer = models.ForeignKey(
        SupplierOffer,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    line_number = models.PositiveIntegerField()
    allocated_quantity = models.DecimalField(
        max_digits=18, decimal_places=3
    )
    base_unit_price_snapshot = models.DecimalField(
        max_digits=20, decimal_places=4
    )
    discount_percent_snapshot = models.DecimalField(
        max_digits=7, decimal_places=4
    )
    net_purchase_price_snapshot = models.DecimalField(
        max_digits=20, decimal_places=4
    )
    allocation_purchase = models.DecimalField(
        max_digits=20, decimal_places=2
    )
    currency = models.CharField(max_length=3, default="IDR")
    supplier_snapshot = models.JSONField()
    offer_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager.from_queryset(AllocationQuerySet)()

    class Meta:
        db_table = "sourcing_supplier_allocation"
        ordering = (
            "procurement_result_item__line_number",
            "line_number",
        )
        constraints = [
            models.UniqueConstraint(
                fields=("procurement_result_item", "line_number"),
                name="sourcing_allocation_line_unique",
            ),
            models.UniqueConstraint(
                fields=("procurement_result_item", "supplier_offer"),
                name="sourcing_allocation_offer_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(line_number__gt=0),
                name="sourcing_allocation_line_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_quantity__gt=0),
                name="sourcing_allocation_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(base_unit_price_snapshot__gt=0),
                name="sourcing_allocation_base_price_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_percent_snapshot__gte=0)
                    & models.Q(discount_percent_snapshot__lte=100)
                ),
                name="sourcing_allocation_discount_bounded",
            ),
            models.CheckConstraint(
                condition=models.Q(net_purchase_price_snapshot__gt=0),
                name="sourcing_allocation_net_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(allocation_purchase__gt=0),
                name="sourcing_allocation_purchase_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IDR"),
                name="sourcing_allocation_currency_idr",
            ),
        ]

    def _assert_draft(self):
        status = ProcurementResult.objects.filter(
            items__pk=self.procurement_result_item_id
        ).values_list("status", flat=True).get()
        if status == ResultStatus.VALID:
            raise ValidationError(
                "Allocation Result VALID tidak dapat diubah."
            )

    def save(self, *args, **kwargs):
        self._assert_draft()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._assert_draft()
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier_offer} / {self.allocated_quantity}"


class SelectionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Selection history tidak dapat diubah.")

    def delete(self):
        raise ValidationError("Selection history tidak dapat dihapus.")


class ProcurementResultSelection(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    tender_request = models.ForeignKey(
        "tender.TenderRequest",
        on_delete=models.PROTECT,
        related_name="result_selections",
    )
    tender_revision = models.ForeignKey(
        "tender.TenderRequestRevision",
        on_delete=models.PROTECT,
        related_name="result_selections",
    )
    procurement_result = models.ForeignKey(
        ProcurementResult,
        on_delete=models.PROTECT,
        related_name="selections",
    )
    selection_number = models.PositiveIntegerField()
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="procurement_result_selections",
    )
    selected_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(SelectionQuerySet)()

    class Meta:
        db_table = "sourcing_procurement_result_selection"
        ordering = ("-selection_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("tender_request", "selection_number"),
                name="sourcing_selection_number_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(selection_number__gt=0),
                name="sourcing_selection_number_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("tender_request", "-selection_number"),
                name="sourcing_selection_current_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Selection history tidak dapat diubah.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Selection history tidak dapat dihapus.")

    def __str__(self):
        return f"{self.tender_request} / selection {self.selection_number}"
