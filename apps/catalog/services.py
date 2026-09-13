"""Transactional application services untuk master data."""

from django.db import IntegrityError, transaction

from apps.accounts.policies import require_admin
from apps.audit.writer import write_audit_event
from apps.core.domain.identifiers import normalize_business_code
from apps.core.exceptions import ConcurrencyConflict

from .choices import CatalogAuditAction
from .models import Product, Supplier

OPTIONAL_TEXT_FIELDS = {
    "description",
    "contact_name",
    "email",
    "phone",
    "address",
}


def _write_event(*, actor, entity, action, correlation_id, metadata=None):
    return write_audit_event(
        actor=actor,
        entity_type=entity.__class__.__name__,
        entity_id=entity.pk,
        entity_revision=entity.version,
        action=action,
        correlation_id=correlation_id,
        metadata=metadata,
    )


def _save_with_conflict(instance, **kwargs):
    try:
        with transaction.atomic():
            instance.save(**kwargs)
    except IntegrityError as error:
        raise ConcurrencyConflict(
            "Data dengan kode tersebut baru saja dibuat atau diubah."
        ) from error


def _normalize_master_values(values):
    normalized = values.copy()
    if "code" in normalized:
        normalized["code"] = normalize_business_code(normalized["code"])
    for field_name in OPTIONAL_TEXT_FIELDS & normalized.keys():
        normalized[field_name] = str(normalized[field_name] or "").strip()
    return normalized


def _create_master(*, model, actor, correlation_id, action, values):
    require_admin(actor)
    values = _normalize_master_values(values)
    with transaction.atomic():
        instance = model(created_by=actor, **values)
        instance.full_clean()
        _save_with_conflict(instance)
        _write_event(
            actor=actor,
            entity=instance,
            action=action,
            correlation_id=correlation_id,
        )
        return instance


def create_product(*, actor, correlation_id, **values):
    return _create_master(
        model=Product,
        actor=actor,
        correlation_id=correlation_id,
        action=CatalogAuditAction.PRODUCT_CREATED,
        values=values,
    )


def create_supplier(*, actor, correlation_id, **values):
    return _create_master(
        model=Supplier,
        actor=actor,
        correlation_id=correlation_id,
        action=CatalogAuditAction.SUPPLIER_CREATED,
        values=values,
    )


def _update_master(
    *,
    model,
    actor,
    entity_id,
    expected_version,
    correlation_id,
    action,
    values,
):
    require_admin(actor)
    values = _normalize_master_values(values)
    with transaction.atomic():
        instance = model.objects.select_for_update().get(pk=entity_id)
        if instance.version != expected_version:
            raise ConcurrencyConflict(
                "Data telah berubah. Muat ulang halaman sebelum menyimpan."
            )
        changed_fields = []
        for field_name, value in values.items():
            if getattr(instance, field_name) != value:
                setattr(instance, field_name, value)
                changed_fields.append(field_name)
        if not changed_fields:
            return instance
        instance.version += 1
        instance.full_clean()
        _save_with_conflict(
            instance,
            update_fields=changed_fields + ["version", "updated_at"]
        )
        _write_event(
            actor=actor,
            entity=instance,
            action=action,
            correlation_id=correlation_id,
            metadata={"changed_fields": changed_fields},
        )
        return instance


def update_product(
    *, actor, product_id, expected_version, correlation_id, **values
):
    return _update_master(
        model=Product,
        actor=actor,
        entity_id=product_id,
        expected_version=expected_version,
        correlation_id=correlation_id,
        action=CatalogAuditAction.PRODUCT_UPDATED,
        values=values,
    )


def update_supplier(
    *, actor, supplier_id, expected_version, correlation_id, **values
):
    return _update_master(
        model=Supplier,
        actor=actor,
        entity_id=supplier_id,
        expected_version=expected_version,
        correlation_id=correlation_id,
        action=CatalogAuditAction.SUPPLIER_UPDATED,
        values=values,
    )


def _deactivate_master(
    *, model, actor, entity_id, expected_version, correlation_id, action
):
    require_admin(actor)
    with transaction.atomic():
        instance = model.objects.select_for_update().get(pk=entity_id)
        if instance.version != expected_version:
            raise ConcurrencyConflict(
                "Data telah berubah. Muat ulang halaman sebelum menyimpan."
            )
        if not instance.is_active:
            return instance
        instance.is_active = False
        instance.version += 1
        instance.save(update_fields=["is_active", "version", "updated_at"])
        _write_event(
            actor=actor,
            entity=instance,
            action=action,
            correlation_id=correlation_id,
        )
        return instance


def deactivate_product(
    *, actor, product_id, expected_version, correlation_id
):
    return _deactivate_master(
        model=Product,
        actor=actor,
        entity_id=product_id,
        expected_version=expected_version,
        correlation_id=correlation_id,
        action=CatalogAuditAction.PRODUCT_DEACTIVATED,
    )


def reactivate_product(
    *, actor, product_id, expected_version, correlation_id
):
    require_admin(actor)
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product_id)
        if product.version != expected_version:
            raise ConcurrencyConflict(
                "Data telah berubah. Muat ulang halaman sebelum menyimpan."
            )
        if product.is_active:
            return product
        product.is_active = True
        product.version += 1
        product.save(
            update_fields=["is_active", "version", "updated_at"]
        )
        _write_event(
            actor=actor,
            entity=product,
            action=CatalogAuditAction.PRODUCT_REACTIVATED,
            correlation_id=correlation_id,
        )
        return product


def deactivate_supplier(
    *, actor, supplier_id, expected_version, correlation_id
):
    return _deactivate_master(
        model=Supplier,
        actor=actor,
        entity_id=supplier_id,
        expected_version=expected_version,
        correlation_id=correlation_id,
        action=CatalogAuditAction.SUPPLIER_DEACTIVATED,
    )
