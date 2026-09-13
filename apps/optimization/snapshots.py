from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.utils import timezone

from apps.core.domain.canonical_json import canonical_hash
from apps.sourcing.models import SupplierOffer
from apps.sourcing.selectors import evaluate_current_offer
from apps.sourcing.snapshots import (
    build_offer_snapshot,
    build_supplier_snapshot,
    decimal_string,
    timestamp_string,
)

from .contracts import OptimizationItem, OptimizationOffer

SNAPSHOT_SCHEMA_VERSION = 1


def build_optimization_input_snapshot(*, revision, captured_at=None):
    captured_at = captured_at or timezone.now()
    as_of_date = timezone.localdate(captured_at)
    items = list(revision.items.select_related("product"))
    product_ids = {item.product_id for item in items}
    offers = SupplierOffer.objects.filter(
        product_id__in=product_ids
    ).select_related("supplier", "product")
    eligible_offers = [
        offer
        for offer in offers
        if evaluate_current_offer(
            offer,
            as_of_date=as_of_date,
            product_id=offer.product_id,
            currency=revision.currency,
        ).eligible
    ]
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_type": "optimization_input",
        "captured_at": timestamp_string(captured_at),
        "evaluation_date": as_of_date.isoformat(),
        "source": {
            "tender_request_id": str(revision.tender_request_id),
            "tender_revision_id": str(revision.pk),
            "revision": revision.revision_number,
        },
        "data": {
            "currency": revision.currency,
            "requirements": [
                {
                    "item_id": str(item.pk),
                    "line_number": item.line_number,
                    "product": item.product_snapshot,
                    "requested_quantity": decimal_string(
                        item.requested_quantity, "0.001"
                    ),
                    "unit": item.unit,
                }
                for item in items
            ],
            "eligible_offers": [
                {
                    **build_offer_snapshot(offer),
                    "supplier": build_supplier_snapshot(offer.supplier),
                    "supplier_code": offer.supplier.code,
                    "offer_active": offer.is_active,
                    "product_active": offer.product.is_active,
                    "supplier_active": offer.supplier.is_active,
                }
                for offer in eligible_offers
            ],
        },
    }
    return snapshot, canonical_hash(snapshot)


def parse_optimization_input_snapshot(snapshot):
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
        or snapshot.get("snapshot_type") != "optimization_input"
    ):
        raise ValueError("Schema snapshot optimization tidak didukung.")
    try:
        data = snapshot["data"]
        requirements = data["requirements"]
        offers = data["eligible_offers"]
        evaluation_date = date.fromisoformat(snapshot["evaluation_date"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Snapshot optimization tidak lengkap.") from error

    offers_by_product = defaultdict(list)
    raw_offers = {}
    try:
        for raw in offers:
            offer_id = str(raw["offer_id"])
            raw_offers[offer_id] = raw
            offers_by_product[str(raw["product_id"])].append(
                OptimizationOffer(
                    offer_id=offer_id,
                    supplier_id=str(raw["supplier_id"]),
                    supplier_code=str(raw["supplier_code"]),
                    product_id=str(raw["product_id"]),
                    net_purchase_price=Decimal(
                        raw["net_purchase_price"]
                    ),
                    available_quantity=(
                        Decimal(raw["available_quantity"])
                        if raw.get("available_quantity") is not None
                        else None
                    ),
                )
            )
        items = []
        raw_requirements = {}
        for raw in requirements:
            item_id = str(raw["item_id"])
            product_id = str(raw["product"]["product_id"])
            raw_requirements[item_id] = raw
            items.append(
                OptimizationItem(
                    tender_item_id=item_id,
                    product_id=product_id,
                    requested_quantity=Decimal(
                        raw["requested_quantity"]
                    ),
                    offers=tuple(offers_by_product[product_id]),
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "Nilai snapshot optimization tidak valid."
        ) from error
    return {
        "items": tuple(items),
        "requirements": raw_requirements,
        "offers": raw_offers,
        "evaluation_date": evaluation_date,
        "currency": data.get("currency"),
    }
