"""Master Product dan Supplier."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Product(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    default_unit = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_product"
        ordering = ("name", "code")
        indexes = [models.Index(fields=("is_active", "name"))]
        constraints = [
            models.UniqueConstraint(
                Lower("code"), name="catalog_product_code_ci_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="catalog_product_version_positive",
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Supplier(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_suppliers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_supplier"
        ordering = ("name", "code")
        indexes = [models.Index(fields=("is_active", "name"))]
        constraints = [
            models.UniqueConstraint(
                Lower("code"), name="catalog_supplier_code_ci_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="catalog_supplier_version_positive",
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"
