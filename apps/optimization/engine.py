"""Pure, deterministic bounded optimizer."""

import hashlib
import heapq
from decimal import Decimal

from apps.core.domain.canonical_json import canonical_dumps
from apps.sourcing.calculations import (
    calculate_allocation_purchase,
    normalize_quantity,
)

from .contracts import (
    CandidateAllocation,
    CandidateRejection,
    OptimizationCandidate,
    OptimizationOutcome,
)

ALGORITHM_VERSION = "greedy-bounded-v1"
DEFAULT_EXPLORATION_LIMIT = 2_000


def candidate_identifier(allocations):
    ordered = sorted(
        (
            allocation.tender_item_id,
            allocation.offer_id,
            format(
                normalize_quantity(allocation.allocated_quantity), "f"
            ),
        )
        for allocation in allocations
    )
    payload = canonical_dumps(ordered).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _rejection_identifier(skip_vector):
    payload = canonical_dumps(
        {"candidate_seed": list(skip_vector)}
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ordered_offers(item):
    return tuple(
        sorted(
            item.offers,
            key=lambda offer: (
                offer.net_purchase_price,
                offer.supplier_code,
                offer.offer_id,
            ),
        )
    )


def _build_candidate(items, skip_vector):
    remaining_capacity = {}
    allocations = []
    suppliers = set()
    total_purchase = Decimal("0.00")

    for item_index, item in enumerate(items):
        quantity_left = normalize_quantity(item.requested_quantity)
        offers = _ordered_offers(item)[skip_vector[item_index] :]
        for offer in offers:
            if quantity_left <= 0:
                break
            if offer.available_quantity is None:
                available = quantity_left
            else:
                available = remaining_capacity.setdefault(
                    offer.offer_id,
                    normalize_quantity(offer.available_quantity),
                )
            allocated = min(quantity_left, available)
            if allocated <= 0:
                continue
            allocations.append(
                CandidateAllocation(
                    tender_item_id=item.tender_item_id,
                    offer_id=offer.offer_id,
                    allocated_quantity=allocated,
                )
            )
            suppliers.add(offer.supplier_id)
            total_purchase += calculate_allocation_purchase(
                allocated, offer.net_purchase_price
            )
            quantity_left -= allocated
            if offer.available_quantity is not None:
                remaining_capacity[offer.offer_id] -= allocated
        if quantity_left > 0:
            return None, CandidateRejection(
                candidate_identifier=_rejection_identifier(skip_vector),
                reason_code="INSUFFICIENT_CAPACITY",
                safe_detail={
                    "tender_item_id": item.tender_item_id,
                    "unfulfilled_quantity": format(quantity_left, "f"),
                },
            )

    ordered_allocations = tuple(
        sorted(
            allocations,
            key=lambda value: (
                value.tender_item_id,
                value.offer_id,
            ),
        )
    )
    identifier = candidate_identifier(ordered_allocations)
    return (
        OptimizationCandidate(
            identifier=identifier,
            allocations=ordered_allocations,
            total_purchase=total_purchase,
            distinct_supplier_count=len(suppliers),
        ),
        None,
    )


def _validate_input(items):
    seen_items = set()
    offer_products = {}
    for item in items:
        if item.tender_item_id in seen_items:
            raise ValueError(
                "Tender item pada input optimizer harus unik."
            )
        seen_items.add(item.tender_item_id)
        if normalize_quantity(item.requested_quantity) <= 0:
            raise ValueError("Jumlah kebutuhan harus lebih dari nol.")
        seen_offers = set()
        for offer in item.offers:
            if offer.offer_id in seen_offers:
                raise ValueError("Offer pada setiap item harus unik.")
            seen_offers.add(offer.offer_id)
            if offer.product_id != item.product_id:
                raise ValueError("Produk offer tidak sesuai item tender.")
            previous_product = offer_products.setdefault(
                offer.offer_id, offer.product_id
            )
            if previous_product != offer.product_id:
                raise ValueError(
                    "Satu offer tidak boleh memiliki dua produk."
                )
            if offer.net_purchase_price <= 0:
                raise ValueError("Harga net offer harus lebih dari nol.")
            if (
                offer.available_quantity is not None
                and normalize_quantity(offer.available_quantity) <= 0
            ):
                raise ValueError("Kapasitas offer harus lebih dari nol.")


def optimize(
    items,
    *,
    max_results=20,
    exploration_limit=DEFAULT_EXPLORATION_LIMIT,
    should_stop=None,
):
    """Return ranked candidates from a deterministic bounded search."""

    normalized_items = tuple(items)
    _validate_input(normalized_items)
    if not normalized_items or max_results <= 0:
        return OptimizationOutcome((), ())

    initial = tuple(0 for _item in normalized_items)
    pending = [initial]
    queued = {initial}
    candidates = {}
    rejections = {}
    explored = 0

    while pending and explored < exploration_limit:
        if should_stop is not None and should_stop():
            break
        skip_vector = heapq.heappop(pending)
        explored += 1
        candidate, rejection = _build_candidate(
            normalized_items, skip_vector
        )
        if candidate is not None:
            candidates.setdefault(candidate.identifier, candidate)
        elif rejection is not None:
            rejections.setdefault(
                rejection.candidate_identifier, rejection
            )

        for index, item in enumerate(normalized_items):
            next_skip = skip_vector[index] + 1
            if next_skip >= len(item.offers):
                continue
            child = list(skip_vector)
            child[index] = next_skip
            child = tuple(child)
            if child not in queued:
                queued.add(child)
                heapq.heappush(pending, child)

    ranked = sorted(
        candidates.values(),
        key=lambda candidate: (
            candidate.total_purchase,
            candidate.distinct_supplier_count,
            candidate.identifier,
        ),
    )[:max_results]
    return OptimizationOutcome(
        candidates=tuple(ranked),
        rejections=tuple(rejections.values()),
    )


run_optimizer = optimize
