"""Pure validation policy for Procurement Result candidates."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .calculations import (
    calculate_allocation_purchase,
    calculate_item_purchase,
    calculate_total_purchase,
    normalize_quantity,
)
from .policies import (
    OfferEligibilityInput,
    calculate_net_purchase_price,
    evaluate_offer_eligibility,
)


@dataclass(frozen=True)
class RequirementInput:
    tender_item_id: str
    line_number: int
    product_id: str
    requested_quantity: Decimal
    unit: str
    product_snapshot: dict


@dataclass(frozen=True)
class AllocationInput:
    line_number: int
    offer_id: str
    product_id: str
    allocated_quantity: Decimal
    base_unit_price: Decimal
    discount_percent: Decimal
    net_purchase_price: Decimal
    currency: str
    eligibility: OfferEligibilityInput


@dataclass(frozen=True)
class ResultItemInput:
    tender_item_id: str
    line_number: int
    requested_quantity: Decimal
    unit: str
    product_snapshot: dict
    allocations: tuple[AllocationInput, ...]


@dataclass(frozen=True)
class ResultViolation:
    code: str
    message: str
    tender_item_id: str | None = None
    allocation_line: int | None = None


@dataclass(frozen=True)
class AllocationAmount:
    tender_item_id: str
    allocation_line: int
    purchase: Decimal


@dataclass(frozen=True)
class ItemAmount:
    tender_item_id: str
    purchase: Decimal


@dataclass(frozen=True)
class ResultValidation:
    violations: tuple[ResultViolation, ...]
    allocation_amounts: tuple[AllocationAmount, ...]
    item_amounts: tuple[ItemAmount, ...]
    total_purchase: Decimal

    @property
    def is_valid(self):
        return not self.violations


ELIGIBILITY_CODE_MAP = {
    "PRODUCT_INACTIVE": "OFFER_INACTIVE",
    "SUPPLIER_INACTIVE": "OFFER_INACTIVE",
    "NOT_YET_VALID": "OFFER_NOT_YET_VALID",
    "EXPIRED": "OFFER_EXPIRED",
    "NO_AVAILABLE_QUANTITY": "ALLOCATION_EXCEEDS_OFFER_LIMIT",
}


def _violation(code, message, item=None, allocation=None):
    return ResultViolation(
        code=code,
        message=message,
        tender_item_id=(item.tender_item_id if item else None),
        allocation_line=(allocation.line_number if allocation else None),
    )


def _validate_item_shape(requirement, item):
    violations = []
    product_id = str(item.product_snapshot.get("product_id", ""))
    expected_snapshot = requirement.product_snapshot
    if (
        item.line_number != requirement.line_number
        or normalize_quantity(item.requested_quantity)
        != normalize_quantity(requirement.requested_quantity)
        or item.unit != requirement.unit
        or product_id != requirement.product_id
        or item.product_snapshot != expected_snapshot
    ):
        violations.append(
            _violation(
                "CALCULATION_MISMATCH",
                "Snapshot item tidak sesuai dengan revision tender.",
                item,
            )
        )
    return violations


def _validate_allocation(item, requirement, allocation, as_of_date):
    violations = []
    quantity = normalize_quantity(allocation.allocated_quantity)
    if quantity <= 0:
        violations.append(
            _violation(
                "ALLOCATION_NON_POSITIVE",
                "Jumlah allocation harus lebih dari nol.",
                item,
                allocation,
            )
        )
    eligibility = evaluate_offer_eligibility(
        allocation.eligibility,
        as_of_date=as_of_date,
        product_id=requirement.product_id,
        currency="IDR",
    )
    if not eligibility.eligible:
        violations.append(
            _violation(
                ELIGIBILITY_CODE_MAP.get(
                    eligibility.code, eligibility.code
                ),
                eligibility.message,
                item,
                allocation,
            )
        )
    if allocation.product_id != requirement.product_id:
        violations.append(
            _violation(
                "PRODUCT_MISMATCH",
                "Produk offer tidak sesuai dengan item tender.",
                item,
                allocation,
            )
        )
    if allocation.currency != "IDR":
        violations.append(
            _violation(
                "CURRENCY_MISMATCH",
                "Mata uang allocation harus IDR.",
                item,
                allocation,
            )
        )
    expected_net = calculate_net_purchase_price(
        allocation.base_unit_price,
        allocation.discount_percent,
    )
    if expected_net != allocation.net_purchase_price:
        violations.append(
            _violation(
                "CALCULATION_MISMATCH",
                "Harga net offer tidak cocok dengan kalkulasi canonical.",
                item,
                allocation,
            )
        )
    return violations


def validate_result_candidate(
    *, requirements, result_items, as_of_date: date
):
    requirement_map = {
        item.tender_item_id: item for item in requirements
    }
    result_map = {item.tender_item_id: item for item in result_items}
    violations = []
    allocation_amounts = []
    item_amounts = []
    offer_totals = {}
    offer_limits = {}

    for tender_item_id in requirement_map.keys() - result_map.keys():
        violations.append(
            ResultViolation(
                "MISSING_TENDER_ITEM",
                "Item tender belum memiliki allocation.",
                tender_item_id=tender_item_id,
            )
        )
    for tender_item_id in result_map.keys() - requirement_map.keys():
        violations.append(
            ResultViolation(
                "EXTRA_TENDER_ITEM",
                "Result memuat item di luar revision tender.",
                tender_item_id=tender_item_id,
            )
        )

    for tender_item_id in requirement_map.keys() & result_map.keys():
        requirement = requirement_map[tender_item_id]
        item = result_map[tender_item_id]
        violations.extend(_validate_item_shape(requirement, item))
        purchases = []
        allocated_total = Decimal("0.000")
        for allocation in sorted(
            item.allocations, key=lambda value: value.line_number
        ):
            violations.extend(
                _validate_allocation(
                    item, requirement, allocation, as_of_date
                )
            )
            quantity = normalize_quantity(allocation.allocated_quantity)
            allocated_total += quantity
            offer_totals[allocation.offer_id] = (
                offer_totals.get(allocation.offer_id, Decimal("0.000"))
                + quantity
            )
            offer_limits[allocation.offer_id] = (
                allocation.eligibility.available_quantity
            )
            purchase = calculate_allocation_purchase(
                quantity, allocation.net_purchase_price
            )
            purchases.append(purchase)
            allocation_amounts.append(
                AllocationAmount(
                    tender_item_id,
                    allocation.line_number,
                    purchase,
                )
            )
        if allocated_total != normalize_quantity(
            requirement.requested_quantity
        ):
            violations.append(
                _violation(
                    "QUANTITY_NOT_FULFILLED",
                    "Total allocation harus tepat memenuhi jumlah tender.",
                    item,
                )
            )
        item_amounts.append(
            ItemAmount(
                tender_item_id,
                calculate_item_purchase(purchases),
            )
        )

    for offer_id, allocated_total in offer_totals.items():
        limit = offer_limits[offer_id]
        if (
            limit is not None
            and allocated_total > normalize_quantity(limit)
        ):
            violations.append(
                ResultViolation(
                    "ALLOCATION_EXCEEDS_OFFER_LIMIT",
                    "Total allocation offer melebihi jumlah tersedia.",
                )
            )

    return ResultValidation(
        violations=tuple(violations),
        allocation_amounts=tuple(allocation_amounts),
        item_amounts=tuple(item_amounts),
        total_purchase=calculate_total_purchase(
            item.purchase for item in item_amounts
        ),
    )
