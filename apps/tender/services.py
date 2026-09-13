"""Application services untuk aggregate Tender Request."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.policies import require_procurement_staff
from apps.audit.writer import write_audit_event
from apps.catalog.models import Product
from apps.core.domain.canonical_json import canonical_hash
from apps.core.domain.identifiers import normalize_business_code
from apps.core.exceptions import ConcurrencyConflict

from .choices import TenderAuditAction
from .models import TenderRequest, TenderRequestItem, TenderRequestRevision

SNAPSHOT_SCHEMA_VERSION = 1


def build_product_snapshot(product):
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "product_id": str(product.pk),
        "code": product.code,
        "name": product.name,
        "description": product.description,
        "default_unit": product.default_unit,
        "is_active_at_capture": product.is_active,
    }


def _normalize_items(items):
    if not items:
        raise ValidationError(
            {"items": "Tender harus memiliki minimal satu item."}
        )
    normalized = []
    seen_lines = set()
    for raw_item in items:
        line_number = int(raw_item["line_number"])
        if line_number <= 0 or line_number in seen_lines:
            raise ValidationError(
                {"items": "Nomor baris harus positif dan unik."}
            )
        seen_lines.add(line_number)
        quantity = Decimal(raw_item["requested_quantity"])
        if quantity <= 0:
            raise ValidationError(
                {"items": "Quantity harus lebih dari nol."}
            )
        try:
            product = Product.objects.get(
                pk=raw_item["product_id"], is_active=True
            )
        except Product.DoesNotExist as error:
            raise ValidationError(
                {"items": "Product aktif tidak ditemukan."}
            ) from error
        unit = str(raw_item.get("unit") or product.default_unit).strip()
        if not unit:
            raise ValidationError({"items": "Unit wajib diisi."})
        normalized.append(
            {
                "line_number": line_number,
                "product": product,
                "product_snapshot": build_product_snapshot(product),
                "requested_quantity": quantity,
                "unit": unit,
                "specification": str(
                    raw_item.get("specification") or ""
                ).strip(),
                "description": str(
                    raw_item.get("description") or ""
                ).strip(),
            }
        )
    return sorted(normalized, key=lambda item: item["line_number"])


def _revision_payload(*, values, items, revision_number):
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "revision_number": revision_number,
        "tender_reference_number": values.get("tender_reference_number")
        or "",
        "institution_name": values["institution_name"],
        "institution_address": values.get("institution_address") or "",
        "title": values["title"],
        "description": values.get("description") or "",
        "currency": "IDR",
        "total_hps": values.get("total_hps"),
        "revision_reason": values.get("revision_reason") or "",
        "items": [
            {
                "line_number": item["line_number"],
                "product_snapshot": item["product_snapshot"],
                "requested_quantity": item["requested_quantity"],
                "unit": item["unit"],
                "specification": item["specification"],
                "description": item["description"],
            }
            for item in items
        ],
    }


def _validate_revision_values(values, revision_number):
    if not str(values.get("institution_name") or "").strip():
        raise ValidationError(
            {"institution_name": "Nama instansi wajib diisi."}
        )
    if not str(values.get("title") or "").strip():
        raise ValidationError({"title": "Judul tender wajib diisi."})
    total_hps = values.get("total_hps")
    if total_hps is not None and Decimal(total_hps) <= 0:
        raise ValidationError({"total_hps": "HPS harus lebih dari nol."})
    if (
        revision_number > 1
        and not str(values.get("revision_reason") or "").strip()
    ):
        raise ValidationError(
            {"revision_reason": "Alasan revisi wajib diisi."}
        )


def _create_revision(*, tender, actor, revision_number, values, items):
    values = {
        "tender_reference_number": str(
            values.get("tender_reference_number") or ""
        ).strip(),
        "institution_name": str(
            values.get("institution_name") or ""
        ).strip(),
        "institution_address": str(
            values.get("institution_address") or ""
        ).strip(),
        "title": str(values.get("title") or "").strip(),
        "description": str(values.get("description") or "").strip(),
        "total_hps": (
            Decimal(values["total_hps"])
            if values.get("total_hps") is not None
            else None
        ),
        "revision_reason": str(
            values.get("revision_reason") or ""
        ).strip(),
    }
    _validate_revision_values(values, revision_number)
    normalized_items = _normalize_items(items)
    payload = _revision_payload(
        values=values,
        items=normalized_items,
        revision_number=revision_number,
    )
    revision = TenderRequestRevision(
        tender_request=tender,
        revision_number=revision_number,
        tender_reference_number=values["tender_reference_number"],
        institution_name=values["institution_name"],
        institution_address=values["institution_address"],
        title=values["title"],
        description=values["description"],
        currency="IDR",
        total_hps=values.get("total_hps"),
        revision_reason=values["revision_reason"],
        content_hash=canonical_hash(payload),
        created_by=actor,
    )
    revision.full_clean()
    revision.save()
    for item in normalized_items:
        tender_item = TenderRequestItem(
            tender_revision=revision,
            **item,
        )
        tender_item.full_clean()
        tender_item.save()
    return revision


def create_tender(
    *, actor, internal_code, items, correlation_id, **revision_values
):
    require_procurement_staff(actor)
    with transaction.atomic():
        tender = TenderRequest(
            internal_code=normalize_business_code(internal_code),
            created_by=actor,
        )
        tender.full_clean()
        try:
            with transaction.atomic():
                tender.save()
        except IntegrityError as error:
            raise ConcurrencyConflict(
                "Kode tender baru saja digunakan oleh proses lain."
            ) from error
        revision = _create_revision(
            tender=tender,
            actor=actor,
            revision_number=1,
            values=revision_values,
            items=items,
        )
        write_audit_event(
            actor=actor,
            entity_type="TenderRequest",
            entity_id=tender.pk,
            entity_revision=1,
            action=TenderAuditAction.TENDER_CREATED,
            correlation_id=correlation_id,
            metadata={"content_hash": revision.content_hash},
        )
        return tender


def revise_tender(
    *, actor, tender_id, expected_version, items, correlation_id, **values
):
    require_procurement_staff(actor)
    with transaction.atomic():
        tender = TenderRequest.objects.select_for_update().get(
            pk=tender_id
        )
        if tender.version != expected_version:
            raise ConcurrencyConflict(
                "Tender telah berubah. Muat ulang halaman."
            )
        next_revision = tender.current_revision_number + 1
        revision = _create_revision(
            tender=tender,
            actor=actor,
            revision_number=next_revision,
            values=values,
            items=items,
        )
        tender.current_revision_number = next_revision
        tender.version += 1
        tender.save(
            update_fields=[
                "current_revision_number",
                "version",
                "updated_at",
            ]
        )
        write_audit_event(
            actor=actor,
            entity_type="TenderRequest",
            entity_id=tender.pk,
            entity_revision=next_revision,
            action=TenderAuditAction.TENDER_REVISED,
            correlation_id=correlation_id,
            reason=revision.revision_reason,
            metadata={"content_hash": revision.content_hash},
        )
        return revision


def get_current_tender_revision(tender_id):
    tender = TenderRequest.objects.only("current_revision_number").get(
        pk=tender_id
    )
    return TenderRequestRevision.objects.prefetch_related(
        "items__product"
    ).get(
        tender_request_id=tender_id,
        revision_number=tender.current_revision_number,
    )
