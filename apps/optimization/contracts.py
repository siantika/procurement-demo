from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OptimizationOffer:
    offer_id: str
    supplier_id: str
    supplier_code: str
    product_id: str
    net_purchase_price: Decimal
    available_quantity: Decimal | None


@dataclass(frozen=True)
class OptimizationItem:
    tender_item_id: str
    product_id: str
    requested_quantity: Decimal
    offers: tuple[OptimizationOffer, ...]


@dataclass(frozen=True)
class CandidateAllocation:
    tender_item_id: str
    offer_id: str
    allocated_quantity: Decimal


@dataclass(frozen=True)
class OptimizationCandidate:
    identifier: str
    allocations: tuple[CandidateAllocation, ...]
    total_purchase: Decimal
    distinct_supplier_count: int


@dataclass(frozen=True)
class CandidateRejection:
    candidate_identifier: str
    reason_code: str
    safe_detail: dict


@dataclass(frozen=True)
class OptimizationOutcome:
    candidates: tuple[OptimizationCandidate, ...]
    rejections: tuple[CandidateRejection, ...]
