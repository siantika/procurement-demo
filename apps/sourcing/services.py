"""Transactional application services untuk Supplier Offer."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.policies import require_procurement_staff
from apps.audit.writer import write_audit_event
from apps.catalog.models import Product, Supplier
from apps.core.exceptions import ConcurrencyConflict

from .choices import OfferAuditAction
from .models import SupplierOffer
from .policies import CALCULATION_VERSION, calculate_net_purchase_price
from .selectors import offer_has_historical_reference

OFFER_MUTABLE_FIELDS = (
    "supplier_reference",
    "base_unit_price",
    "discount_percent",
    "available_quantity",
    "valid_from",
    "valid_until",
)


def _active_master(model, entity_id, label):
    try:
        return model.objects.get(pk=entity_id, is_active=True)
    except model.DoesNotExist as error:
        raise ValidationError(
            {label: f"{label.title()} aktif tidak ditemukan."}
        ) from error


def _offer_values(*, supplier_id, product_id, values):
    supplier = _active_master(Supplier, supplier_id, "supplier")
    product = _active_master(Product, product_id, "product")
    cleaned = {field: values.get(field) for field in OFFER_MUTABLE_FIELDS}
    cleaned["supplier_reference"] = str(
        cleaned["supplier_reference"] or ""
    ).strip()
    cleaned.update(
        supplier=supplier,
        product=product,
        net_purchase_price=calculate_net_purchase_price(
            cleaned["base_unit_price"], cleaned["discount_percent"]
        ),
        currency="IDR",
        calculation_version=CALCULATION_VERSION,
    )
    return cleaned


def _write_event(*, actor, offer, action, correlation_id, metadata=None):
    write_audit_event(
        actor=actor,
        entity_type="SupplierOffer",
        entity_id=offer.pk,
        entity_revision=offer.version,
        action=action,
        correlation_id=correlation_id,
        metadata=metadata,
    )


def create_supplier_offer(
    *, actor, supplier_id, product_id, correlation_id, **values
):
    require_procurement_staff(actor)
    with transaction.atomic():
        offer = SupplierOffer(
            created_by=actor,
            **_offer_values(
                supplier_id=supplier_id,
                product_id=product_id,
                values=values,
            ),
        )
        offer.full_clean()
        offer.save()
        _write_event(
            actor=actor,
            offer=offer,
            action=OfferAuditAction.OFFER_CREATED,
            correlation_id=correlation_id,
        )
        return offer


def _offer_identity(offer, values):
    supplier_id = values.get("supplier_id", offer.supplier_id)
    product_id = values.get("product_id", offer.product_id)
    errors = {}
    if str(supplier_id) != str(offer.supplier_id):
        errors["supplier"] = (
            "Supplier tidak dapat diubah; buat offer baru untuk "
            "supplier lain."
        )
    if str(product_id) != str(offer.product_id):
        errors["product"] = (
            "Produk tidak dapat diubah; buat offer baru untuk produk lain."
        )
    if errors:
        raise ValidationError(errors)
    return offer.supplier_id, offer.product_id


def correct_unused_offer(
    *, actor, offer_id, expected_version, correlation_id, **values
):
    require_procurement_staff(actor)
    with transaction.atomic():
        offer = SupplierOffer.objects.select_for_update().get(pk=offer_id)
        if offer.version != expected_version:
            raise ConcurrencyConflict(
                "Offer telah berubah. Muat ulang halaman."
            )
        if offer_has_historical_reference(offer):
            raise ValidationError(
                "Offer yang sudah memiliki histori harus disupersede."
            )
        supplier_id, product_id = _offer_identity(offer, values)
        updated = _offer_values(
            supplier_id=supplier_id,
            product_id=product_id,
            values={
                field: values.get(field, getattr(offer, field))
                for field in OFFER_MUTABLE_FIELDS
            },
        )
        changed_fields = []
        for field_name, value in updated.items():
            if getattr(offer, field_name) != value:
                setattr(offer, field_name, value)
                changed_fields.append(field_name)
        if not changed_fields:
            return offer
        offer.version += 1
        offer.full_clean()
        offer.save(
            update_fields=changed_fields + ["version", "updated_at"]
        )
        _write_event(
            actor=actor,
            offer=offer,
            action=OfferAuditAction.OFFER_CORRECTED,
            correlation_id=correlation_id,
            metadata={"changed_fields": changed_fields},
        )
        return offer


def supersede_supplier_offer(
    *, actor, offer_id, expected_version, correlation_id, **values
):
    require_procurement_staff(actor)
    with transaction.atomic():
        old_offer = SupplierOffer.objects.select_for_update().get(
            pk=offer_id
        )
        if old_offer.version != expected_version:
            raise ConcurrencyConflict(
                "Offer telah berubah. Muat ulang halaman."
            )
        if hasattr(old_offer, "superseding_offer"):
            raise ValidationError("Offer ini sudah pernah disupersede.")
        supplier_id, product_id = _offer_identity(old_offer, values)
        new_offer = SupplierOffer(
            created_by=actor,
            supersedes_offer=old_offer,
            **_offer_values(
                supplier_id=supplier_id,
                product_id=product_id,
                values={
                    field: values.get(field, getattr(old_offer, field))
                    for field in OFFER_MUTABLE_FIELDS
                },
            ),
        )
        new_offer.full_clean()
        new_offer.save()
        if old_offer.is_active:
            old_offer.is_active = False
            old_offer.version += 1
            old_offer.save(
                update_fields=["is_active", "version", "updated_at"]
            )
        _write_event(
            actor=actor,
            offer=old_offer,
            action=OfferAuditAction.OFFER_SUPERSEDED,
            correlation_id=correlation_id,
            metadata={"replacement_offer_id": str(new_offer.pk)},
        )
        _write_event(
            actor=actor,
            offer=new_offer,
            action=OfferAuditAction.OFFER_CREATED,
            correlation_id=correlation_id,
            metadata={"supersedes_offer_id": str(old_offer.pk)},
        )
        return new_offer


def deactivate_supplier_offer(
    *, actor, offer_id, expected_version, correlation_id
):
    require_procurement_staff(actor)
    with transaction.atomic():
        offer = SupplierOffer.objects.select_for_update().get(pk=offer_id)
        if offer.version != expected_version:
            raise ConcurrencyConflict(
                "Offer telah berubah. Muat ulang halaman."
            )
        if not offer.is_active:
            return offer
        offer.is_active = False
        offer.version += 1
        offer.save(update_fields=["is_active", "version", "updated_at"])
        _write_event(
            actor=actor,
            offer=offer,
            action=OfferAuditAction.OFFER_DEACTIVATED,
            correlation_id=correlation_id,
        )
        return offer
