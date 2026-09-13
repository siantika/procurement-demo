"""Snapshot builders for immutable Procurement Result history."""

from decimal import Decimal

SNAPSHOT_SCHEMA_VERSION = 1
ROUNDING_POLICY_VERSION = "idr-half-up-v1"


def decimal_string(value, scale):
    if value is None:
        return None
    return format(Decimal(value).quantize(Decimal(scale)), "f")


def timestamp_string(value):
    return value.isoformat().replace("+00:00", "Z")


def build_supplier_snapshot(supplier):
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "supplier_id": str(supplier.pk),
        "code": supplier.code,
        "name": supplier.name,
        "contact_name": supplier.contact_name,
        "email": supplier.email,
        "phone": supplier.phone,
        "address": supplier.address,
    }


def build_offer_snapshot(offer):
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "offer_id": str(offer.pk),
        "supplier_id": str(offer.supplier_id),
        "product_id": str(offer.product_id),
        "supplier_reference": offer.supplier_reference,
        "base_unit_price": decimal_string(
            offer.base_unit_price, "0.0001"
        ),
        "discount_percent": decimal_string(
            offer.discount_percent, "0.0001"
        ),
        "net_purchase_price": decimal_string(
            offer.net_purchase_price, "0.0001"
        ),
        "available_quantity": decimal_string(
            offer.available_quantity, "0.001"
        ),
        "currency": offer.currency,
        "valid_from": (
            offer.valid_from.isoformat() if offer.valid_from else None
        ),
        "valid_until": (
            offer.valid_until.isoformat() if offer.valid_until else None
        ),
        "calculation_version": offer.calculation_version,
    }


def build_procurement_result_snapshot(
    *, result, tender_revision, items, captured_at
):
    tender = tender_revision.tender_request
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_type": "procurement_result",
        "captured_at": timestamp_string(captured_at),
        "source": {
            "result_id": str(result.pk),
            "source_type": result.source_type,
            "source_result_id": (
                str(result.source_result_id)
                if result.source_result_id
                else None
            ),
            "optimization_run_id": (
                str(result.optimization_run_id)
                if result.optimization_run_id
                else None
            ),
            "rank": result.rank,
            "tender_request_id": str(tender.pk),
            "tender_revision_id": str(tender_revision.pk),
            "tender_revision_number": tender_revision.revision_number,
        },
        "tender": {
            "internal_code": tender.internal_code,
            "tender_reference_number": (
                tender_revision.tender_reference_number
            ),
            "institution_name": tender_revision.institution_name,
            "institution_address": tender_revision.institution_address,
            "title": tender_revision.title,
            "description": tender_revision.description,
            "total_hps": decimal_string(
                tender_revision.total_hps, "0.01"
            ),
            "currency": tender_revision.currency,
        },
        "data": {
            "currency": result.currency,
            "calculation_version": result.calculation_version,
            "rounding_policy_version": ROUNDING_POLICY_VERSION,
            "total_purchase": decimal_string(
                result.total_purchase, "0.01"
            ),
            "items": items,
        },
    }
