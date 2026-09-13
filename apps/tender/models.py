"""Tender root dan revision historis yang immutable."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Revision tender tidak dapat diubah.")

    def delete(self):
        raise ValidationError("Revision tender tidak dapat dihapus.")


class TenderRequest(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    internal_code = models.CharField(max_length=50, unique=True)
    current_revision_number = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tenders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tender_tender_request"
        ordering = ("-created_at", "internal_code")
        indexes = [models.Index(fields=("created_at",))]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(current_revision_number__gt=0),
                name="tender_current_revision_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="tender_version_positive",
            ),
        ]

    def __str__(self):
        return self.internal_code


class ImmutableModel(models.Model):
    objects = models.Manager.from_queryset(ImmutableQuerySet)()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Revision tender tidak dapat diubah.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Revision tender tidak dapat dihapus.")


class TenderRequestRevision(ImmutableModel):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    tender_request = models.ForeignKey(
        TenderRequest,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    tender_reference_number = models.CharField(max_length=100, blank=True)
    institution_name = models.CharField(max_length=255)
    institution_address = models.TextField(blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default="IDR")
    total_hps = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
    )
    revision_reason = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tender_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tender_tender_request_revision"
        ordering = ("-revision_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("tender_request", "revision_number"),
                name="tender_revision_number_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(revision_number__gt=0),
                name="tender_revision_number_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(total_hps__isnull=True)
                    | models.Q(total_hps__gt=0)
                ),
                name="tender_revision_hps_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IDR"),
                name="tender_revision_currency_idr",
            ),
        ]

    def __str__(self):
        return (
            f"{self.tender_request.internal_code} R{self.revision_number}"
        )


class TenderRequestItem(ImmutableModel):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    tender_revision = models.ForeignKey(
        TenderRequestRevision,
        on_delete=models.CASCADE,
        related_name="items",
    )
    line_number = models.PositiveIntegerField()
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="tender_items",
    )
    product_snapshot = models.JSONField()
    requested_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=3,
    )
    unit = models.CharField(max_length=32)
    specification = models.TextField(blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tender_tender_request_item"
        ordering = ("line_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("tender_revision", "line_number"),
                name="tender_item_line_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(line_number__gt=0),
                name="tender_item_line_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_quantity__gt=0),
                name="tender_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.tender_revision} / {self.line_number}"
