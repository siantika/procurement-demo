"""Supplier Offer sebagai data komersial versioned."""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
