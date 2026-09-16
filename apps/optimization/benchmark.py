"""Reproducible, engine-only benchmark for the bounded optimizer."""

import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from datetime import date
from decimal import Decimal

import django

from apps.core.domain.canonical_json import canonical_hash
from apps.sourcing.policies import OfferEligibilityInput
from apps.sourcing.validators import (
    AllocationInput,
    RequirementInput,
    ResultItemInput,
    validate_result_candidate,
)

from .contracts import OptimizationItem, OptimizationOffer
from .engine import ALGORITHM_VERSION, optimize

BENCHMARK_DATE = date(2026, 1, 1)


def build_synthetic_dataset(*, items, offers_per_item, seed):
    """Build deterministic inputs without database or network access."""

    generator = random.Random(seed)
    dataset = []
    for item_index in range(items):
        product_id = f"product-{item_index:04d}"
        offers = []
        for offer_index in range(offers_per_item):
            price_offset = generator.randint(0, 500_000)
            capacity = generator.randint(30, 100)
            offers.append(
                OptimizationOffer(
                    offer_id=(
                        f"offer-{item_index:04d}-{offer_index:04d}"
                    ),
                    supplier_id=f"supplier-{offer_index % 10:02d}",
                    supplier_code=f"SUP-{offer_index % 10:02d}",
                    product_id=product_id,
                    net_purchase_price=Decimal(
                        1_000_000 + price_offset + offer_index
                    ).quantize(Decimal("0.0001")),
                    available_quantity=Decimal(capacity).quantize(
                        Decimal("0.001")
                    ),
                )
            )
        dataset.append(
            OptimizationItem(
                tender_item_id=f"item-{item_index:04d}",
                product_id=product_id,
                requested_quantity=Decimal("100.000"),
                offers=tuple(offers),
            )
        )
    return tuple(dataset)


def _candidate_validation(items, candidate):
    offer_map = {
        offer.offer_id: offer
        for item in items
        for offer in item.offers
    }
    allocations_by_item = {}
    for allocation in candidate.allocations:
        allocations_by_item.setdefault(
            allocation.tender_item_id, []
        ).append(allocation)

    requirements = []
    result_items = []
    for line_number, item in enumerate(items, start=1):
        product_snapshot = {
            "product_id": item.product_id,
            "name": f"Synthetic product {line_number}",
            "unit": "unit",
        }
        requirements.append(
            RequirementInput(
                tender_item_id=item.tender_item_id,
                line_number=line_number,
                product_id=item.product_id,
                requested_quantity=item.requested_quantity,
                unit="unit",
                product_snapshot=product_snapshot,
            )
        )
        allocation_inputs = []
        for allocation_line, allocation in enumerate(
            allocations_by_item.get(item.tender_item_id, ()), start=1
        ):
            offer = offer_map[allocation.offer_id]
            allocation_inputs.append(
                AllocationInput(
                    line_number=allocation_line,
                    offer_id=offer.offer_id,
                    product_id=offer.product_id,
                    allocated_quantity=allocation.allocated_quantity,
                    base_unit_price=offer.net_purchase_price,
                    discount_percent=Decimal("0.0000"),
                    net_purchase_price=offer.net_purchase_price,
                    currency="IDR",
                    eligibility=OfferEligibilityInput(
                        offer_active=True,
                        product_active=True,
                        supplier_active=True,
                        product_id=offer.product_id,
                        currency="IDR",
                        net_purchase_price=offer.net_purchase_price,
                        available_quantity=offer.available_quantity,
                        valid_from=None,
                        valid_until=None,
                    ),
                )
            )
        result_items.append(
            ResultItemInput(
                tender_item_id=item.tender_item_id,
                line_number=line_number,
                requested_quantity=item.requested_quantity,
                unit="unit",
                product_snapshot=product_snapshot,
                allocations=tuple(allocation_inputs),
            )
        )

    validation = validate_result_candidate(
        requirements=tuple(requirements),
        result_items=tuple(result_items),
        as_of_date=BENCHMARK_DATE,
    )
    return (
        validation.is_valid
        and validation.total_purchase == candidate.total_purchase
    )


def _outcome_checksum(outcome):
    return canonical_hash(
        [
            {
                "identifier": candidate.identifier,
                "total_purchase": candidate.total_purchase,
                "distinct_supplier_count": (
                    candidate.distinct_supplier_count
                ),
                "allocations": [
                    {
                        "tender_item_id": allocation.tender_item_id,
                        "offer_id": allocation.offer_id,
                        "allocated_quantity": (
                            allocation.allocated_quantity
                        ),
                    }
                    for allocation in candidate.allocations
                ],
            }
            for candidate in outcome.candidates
        ]
    )


def _percentile(values, percentile):
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _git_metadata():
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return {"commit_sha": "unknown", "working_tree_dirty": None}
    return {
        "commit_sha": revision.stdout.strip() or "unknown",
        "working_tree_dirty": bool(status.stdout.strip()),
    }


def run_benchmark(
    *,
    items,
    offers_per_item,
    seed,
    warmups,
    runs,
    max_results,
    exploration_limit,
):
    """Measure the existing engine without changing its decisions."""

    dataset = build_synthetic_dataset(
        items=items,
        offers_per_item=offers_per_item,
        seed=seed,
    )
    optimizer_options = {
        "max_results": max_results,
        "exploration_limit": exploration_limit,
    }
    for _iteration in range(warmups):
        optimize(dataset, **optimizer_options)

    measurements = []
    expected_checksum = None
    for sequence in range(1, runs + 1):
        started_at = time.perf_counter_ns()
        outcome = optimize(dataset, **optimizer_options)
        duration_ns = time.perf_counter_ns() - started_at
        checksum = _outcome_checksum(outcome)
        valid = all(
            _candidate_validation(dataset, candidate)
            for candidate in outcome.candidates
        )
        if not valid:
            raise RuntimeError(
                "Kandidat benchmark gagal shared result validation."
            )
        if expected_checksum is None:
            expected_checksum = checksum
        elif checksum != expected_checksum:
            raise RuntimeError(
                "Output optimizer tidak deterministik antar-run."
            )
        measurements.append(
            {
                "run": sequence,
                "duration_ms": duration_ns / 1_000_000,
                "explored_vectors": outcome.stats.explored_vectors,
                "valid_candidates_discovered": (
                    outcome.stats.valid_candidates_discovered
                ),
                "rejected_candidates_discovered": (
                    outcome.stats.rejected_candidates_discovered
                ),
                "exploration_limit_reached": (
                    outcome.stats.exploration_limit_reached
                ),
                "result_count": len(outcome.candidates),
                "validation_status": "valid",
                "result_checksum": checksum,
            }
        )

    tracemalloc.start()
    optimize(dataset, **optimizer_options)
    _current_bytes, peak_python_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    durations = [item["duration_ms"] for item in measurements]
    mean_duration = statistics.fmean(durations)
    deviation = statistics.pstdev(durations)
    git_metadata = _git_metadata()
    return {
        "benchmark": "procurement-optimizer-performance",
        "algorithm_version": ALGORITHM_VERSION,
        **git_metadata,
        "runtime": {
            "python": platform.python_version(),
            "django": django.get_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "executable": sys.executable,
        },
        "parameters": {
            "items": items,
            "offers_per_item": offers_per_item,
            "total_offers": items * offers_per_item,
            "seed": seed,
            "warmups": warmups,
            "runs": runs,
            "max_results": max_results,
            "exploration_limit": exploration_limit,
        },
        "runs": measurements,
        "summary": {
            "minimum_ms": min(durations),
            "median_ms": statistics.median(durations),
            "p95_ms": _percentile(durations, 0.95),
            "maximum_ms": max(durations),
            "mean_ms": mean_duration,
            "standard_deviation_ms": deviation,
            "coefficient_of_variation_percent": (
                deviation / mean_duration * 100
                if mean_duration
                else 0.0
            ),
            "peak_python_allocated_bytes": peak_python_bytes,
            "deterministic": True,
            "validation_status": "valid",
            "result_checksum": expected_checksum,
        },
    }
