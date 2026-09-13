"""Transactional application services for optimization runs."""

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.policies import require_procurement_staff
from apps.audit.writer import write_audit_event
from apps.core.domain.canonical_json import canonical_hash
from apps.core.exceptions import InvalidTransition
from apps.notifications.choices import NotificationType
from apps.notifications.services import create_notification
from apps.sourcing.calculations import CALCULATION_VERSION
from apps.sourcing.choices import (
    ResultAuditAction,
    ResultSourceType,
    ResultStatus,
)
from apps.sourcing.models import (
    ProcurementResult,
    ProcurementResultItem,
    SupplierAllocation,
    SupplierOffer,
)
from apps.sourcing.policies import OfferEligibilityInput
from apps.sourcing.snapshots import (
    SNAPSHOT_SCHEMA_VERSION as RESULT_SNAPSHOT_SCHEMA_VERSION,
)
from apps.sourcing.snapshots import build_procurement_result_snapshot
from apps.sourcing.validators import (
    AllocationInput,
    RequirementInput,
    ResultItemInput,
    validate_result_candidate,
)
from apps.tender.models import TenderRequest

from .choices import OptimizationAuditAction, OptimizationStatus
from .engine import ALGORITHM_VERSION, optimize
from .models import OptimizationCandidateRejection, OptimizationRun
from .snapshots import (
    SNAPSHOT_SCHEMA_VERSION,
    build_optimization_input_snapshot,
    parse_optimization_input_snapshot,
)

logger = logging.getLogger(__name__)


def _write_run_event(
    *,
    run,
    action,
    correlation_id,
    actor=None,
    from_status=None,
    to_status=None,
):
    return write_audit_event(
        actor=actor,
        entity_type="OptimizationRun",
        entity_id=run.pk,
        entity_revision=run.version,
        action=action,
        correlation_id=correlation_id,
        from_status=from_status,
        to_status=to_status,
        metadata={
            "tender_request_id": str(run.tender_request_id),
            "tender_revision_id": str(run.tender_revision_id),
            "algorithm_version": run.algorithm_version,
        },
    )


def publish_optimization_run(run_id, correlation_id=None):
    from .tasks import execute_optimization_run

    execute_optimization_run.delay(
        str(run_id), str(correlation_id or run_id)
    )


def _publish_safely(run_id, correlation_id):
    try:
        publish_optimization_run(run_id, correlation_id)
    except Exception:
        logger.exception(
            "Optimization task publish failed; reconciliation will retry",
            extra={"optimization_run_id": str(run_id)},
        )


def _assert_limits(snapshot):
    requirements = snapshot["data"]["requirements"]
    offers = snapshot["data"]["eligible_offers"]
    max_items = settings.OPTIMIZER_MAX_ITEMS
    max_offers = settings.OPTIMIZER_MAX_OFFERS_PER_ITEM
    if len(requirements) > max_items:
        raise ValidationError(
            {"tender": f"Tender melebihi batas {max_items} item."}
        )
    offer_counts = defaultdict(int)
    for offer in offers:
        offer_counts[str(offer["product_id"])] += 1
    for requirement in requirements:
        product_id = str(requirement["product"]["product_id"])
        if offer_counts[product_id] > max_offers:
            raise ValidationError(
                {
                    "tender": (
                        "Jumlah eligible offer untuk satu item melebihi "
                        f"batas {max_offers}."
                    )
                }
            )


def request_optimization(
    *, actor, tender_request_id, correlation_id, retry_of_run_id=None
):
    require_procurement_staff(actor)
    with transaction.atomic():
        try:
            tender = TenderRequest.objects.select_for_update().get(
                pk=tender_request_id
            )
        except TenderRequest.DoesNotExist as error:
            raise ValidationError(
                {"tender": "Tender tidak ditemukan."}
            ) from error
        if OptimizationRun.objects.filter(
            tender_request=tender,
            status__in=(
                OptimizationStatus.PENDING,
                OptimizationStatus.RUNNING,
            ),
        ).exists():
            raise InvalidTransition(
                "Tender ini masih memiliki optimization aktif."
            )
        revision = tender.revisions.select_related(
            "tender_request"
        ).prefetch_related("items__product").get(
            revision_number=tender.current_revision_number
        )
        retry_of = None
        if retry_of_run_id is not None:
            try:
                retry_of = OptimizationRun.objects.get(
                    pk=retry_of_run_id,
                    tender_request=tender,
                    status=OptimizationStatus.FAILED,
                )
            except OptimizationRun.DoesNotExist as error:
                raise ValidationError(
                    {"retry": "Run gagal yang akan di-retry tidak valid."}
                ) from error
        snapshot, input_hash = build_optimization_input_snapshot(
            revision=revision
        )
        _assert_limits(snapshot)
        run = OptimizationRun(
            tender_request=tender,
            tender_revision=revision,
            retry_of_run=retry_of,
            status=OptimizationStatus.PENDING,
            algorithm_version=ALGORITHM_VERSION,
            snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
            input_snapshot=snapshot,
            input_hash=input_hash,
            requested_by=actor,
        )
        run.full_clean(validate_unique=False)
        try:
            run.save()
        except IntegrityError as error:
            raise InvalidTransition(
                "Tender ini masih memiliki optimization aktif."
            ) from error
        _write_run_event(
            run=run,
            actor=actor,
            action=OptimizationAuditAction.REQUESTED,
            correlation_id=correlation_id,
            to_status=OptimizationStatus.PENDING,
        )
        transaction.on_commit(
            lambda: _publish_safely(run.pk, correlation_id)
        )
        return run


def retry_optimization(*, actor, run_id, correlation_id):
    try:
        previous = OptimizationRun.objects.get(pk=run_id)
    except OptimizationRun.DoesNotExist as error:
        raise ValidationError(
            "Optimization run tidak ditemukan."
        ) from error
    return request_optimization(
        actor=actor,
        tender_request_id=previous.tender_request_id,
        retry_of_run_id=previous.pk,
        correlation_id=correlation_id,
    )


def claim_optimization_run(*, run_id, correlation_id):
    with transaction.atomic():
        try:
            run = OptimizationRun.objects.select_for_update().get(
                pk=run_id
            )
        except OptimizationRun.DoesNotExist:
            return None
        if run.status != OptimizationStatus.PENDING:
            return None
        previous_status = run.status
        run.status = OptimizationStatus.RUNNING
        run.started_at = timezone.now()
        run.version += 1
        run.full_clean(validate_unique=False)
        run.save(update_fields=["status", "started_at", "version"])
        _write_run_event(
            run=run,
            action=OptimizationAuditAction.STARTED,
            correlation_id=correlation_id,
            from_status=previous_status,
            to_status=run.status,
        )
        return run


def _date_value(raw):
    return date.fromisoformat(raw) if raw else None


def _offer_input(raw):
    return OfferEligibilityInput(
        offer_active=bool(raw["offer_active"]),
        product_active=bool(raw["product_active"]),
        supplier_active=bool(raw["supplier_active"]),
        product_id=str(raw["product_id"]),
        currency=str(raw["currency"]),
        net_purchase_price=Decimal(raw["net_purchase_price"]),
        available_quantity=(
            Decimal(raw["available_quantity"])
            if raw.get("available_quantity") is not None
            else None
        ),
        valid_from=_date_value(raw.get("valid_from")),
        valid_until=_date_value(raw.get("valid_until")),
    )


def _candidate_validation(candidate, parsed):
    grouped = defaultdict(list)
    for allocation in candidate.allocations:
        grouped[allocation.tender_item_id].append(allocation)
    requirements = []
    result_items = []
    for item in parsed["items"]:
        raw_requirement = parsed["requirements"][item.tender_item_id]
        requirement = RequirementInput(
            tender_item_id=item.tender_item_id,
            line_number=int(raw_requirement["line_number"]),
            product_id=item.product_id,
            requested_quantity=item.requested_quantity,
            unit=str(raw_requirement["unit"]),
            product_snapshot=raw_requirement["product"],
        )
        requirements.append(requirement)
        allocations = []
        for line_number, allocation in enumerate(
            sorted(
                grouped[item.tender_item_id],
                key=lambda row: row.offer_id,
            ),
            start=1,
        ):
            raw_offer = parsed["offers"][allocation.offer_id]
            allocations.append(
                AllocationInput(
                    line_number=line_number,
                    offer_id=allocation.offer_id,
                    product_id=str(raw_offer["product_id"]),
                    allocated_quantity=allocation.allocated_quantity,
                    base_unit_price=Decimal(raw_offer["base_unit_price"]),
                    discount_percent=Decimal(
                        raw_offer["discount_percent"]
                    ),
                    net_purchase_price=Decimal(
                        raw_offer["net_purchase_price"]
                    ),
                    currency=str(raw_offer["currency"]),
                    eligibility=_offer_input(raw_offer),
                )
            )
        result_items.append(
            ResultItemInput(
                tender_item_id=item.tender_item_id,
                line_number=requirement.line_number,
                requested_quantity=requirement.requested_quantity,
                unit=requirement.unit,
                product_snapshot=requirement.product_snapshot,
                allocations=tuple(allocations),
            )
        )
    return validate_result_candidate(
        requirements=tuple(requirements),
        result_items=tuple(result_items),
        as_of_date=parsed["evaluation_date"],
    )


def _public_offer_snapshot(raw):
    keys = (
        "schema_version",
        "offer_id",
        "supplier_id",
        "product_id",
        "supplier_reference",
        "base_unit_price",
        "discount_percent",
        "net_purchase_price",
        "available_quantity",
        "currency",
        "valid_from",
        "valid_until",
        "calculation_version",
    )
    return {key: raw[key] for key in keys}


def _persist_candidate(*, run, candidate, parsed, rank, captured_at):
    validation = _candidate_validation(candidate, parsed)
    if not validation.is_valid:
        return None, {
            "candidate_identifier": candidate.identifier,
            "reason_code": "CANONICAL_VALIDATION_FAILED",
            "safe_detail": {
                "violation_codes": sorted(
                    {item.code for item in validation.violations}
                )
            },
        }
    if validation.total_purchase != candidate.total_purchase:
        return None, {
            "candidate_identifier": candidate.identifier,
            "reason_code": "CALCULATION_MISMATCH",
            "safe_detail": {},
        }

    offer_ids = {
        allocation.offer_id for allocation in candidate.allocations
    }
    live_offers = {
        str(offer.pk): offer
        for offer in SupplierOffer.objects.filter(pk__in=offer_ids)
    }
    if set(live_offers) != offer_ids:
        raise ValueError(
            "Offer snapshot tidak lagi memiliki referensi data."
        )
    result = ProcurementResult.objects.create(
        tender_revision=run.tender_revision,
        source_type=ResultSourceType.OPTIMIZER,
        status=ResultStatus.DRAFT,
        optimization_run=run,
        rank=rank,
        currency=parsed["currency"],
        calculation_version=CALCULATION_VERSION,
        created_by=run.requested_by,
    )
    grouped = defaultdict(list)
    for allocation in candidate.allocations:
        grouped[allocation.tender_item_id].append(allocation)
    allocation_amounts = {
        (amount.tender_item_id, amount.allocation_line): amount.purchase
        for amount in validation.allocation_amounts
    }
    item_amounts = {
        amount.tender_item_id: amount.purchase
        for amount in validation.item_amounts
    }
    snapshot_items = []
    for item in parsed["items"]:
        requirement = parsed["requirements"][item.tender_item_id]
        result_item = ProcurementResultItem.objects.create(
            procurement_result=result,
            tender_request_item_id=item.tender_item_id,
            line_number=int(requirement["line_number"]),
            requested_quantity_snapshot=item.requested_quantity,
            unit_snapshot=requirement["unit"],
            item_purchase_total=item_amounts[item.tender_item_id],
            currency=parsed["currency"],
            product_snapshot=requirement["product"],
        )
        snapshot_allocations = []
        ordered = sorted(
            grouped[item.tender_item_id], key=lambda row: row.offer_id
        )
        for line_number, allocation in enumerate(ordered, start=1):
            raw_offer = parsed["offers"][allocation.offer_id]
            purchase = allocation_amounts[
                (item.tender_item_id, line_number)
            ]
            stored = SupplierAllocation.objects.create(
                procurement_result_item=result_item,
                supplier_offer=live_offers[allocation.offer_id],
                line_number=line_number,
                allocated_quantity=allocation.allocated_quantity,
                base_unit_price_snapshot=Decimal(
                    raw_offer["base_unit_price"]
                ),
                discount_percent_snapshot=Decimal(
                    raw_offer["discount_percent"]
                ),
                net_purchase_price_snapshot=Decimal(
                    raw_offer["net_purchase_price"]
                ),
                allocation_purchase=purchase,
                currency=raw_offer["currency"],
                supplier_snapshot=raw_offer["supplier"],
                offer_snapshot=_public_offer_snapshot(raw_offer),
            )
            snapshot_allocations.append(
                {
                    "allocation_id": str(stored.pk),
                    "line_number": line_number,
                    "offer_id": allocation.offer_id,
                    "supplier": raw_offer["supplier"],
                    "offer": _public_offer_snapshot(raw_offer),
                    "allocated_quantity": format(
                        allocation.allocated_quantity, "f"
                    ),
                    "base_unit_price": raw_offer["base_unit_price"],
                    "discount_percent": raw_offer["discount_percent"],
                    "net_purchase_price": raw_offer["net_purchase_price"],
                    "allocation_purchase": format(purchase, ".2f"),
                    "currency": raw_offer["currency"],
                }
            )
        snapshot_items.append(
            {
                "result_item_id": str(result_item.pk),
                "tender_item_id": item.tender_item_id,
                "line_number": int(requirement["line_number"]),
                "product": requirement["product"],
                "requested_quantity": format(
                    item.requested_quantity, "f"
                ),
                "unit": requirement["unit"],
                "item_purchase_total": format(
                    item_amounts[item.tender_item_id], ".2f"
                ),
                "currency": parsed["currency"],
                "allocations": snapshot_allocations,
            }
        )
    result.total_purchase = validation.total_purchase
    result.snapshot_schema_version = RESULT_SNAPSHOT_SCHEMA_VERSION
    result.validated_at = captured_at
    result.status = ResultStatus.VALID
    result.result_snapshot = build_procurement_result_snapshot(
        result=result,
        tender_revision=run.tender_revision,
        items=snapshot_items,
        captured_at=captured_at,
    )
    result.result_hash = canonical_hash(result.result_snapshot)
    result.full_clean()
    result.save(
        update_fields=[
            "total_purchase",
            "snapshot_schema_version",
            "validated_at",
            "status",
            "result_snapshot",
            "result_hash",
            "updated_at",
        ]
    )
    write_audit_event(
        actor=None,
        entity_type="ProcurementResult",
        entity_id=result.pk,
        entity_revision=result.version,
        action=ResultAuditAction.RESULT_CREATED,
        correlation_id=str(run.pk),
        to_status=ResultStatus.VALID,
        metadata={
            "tender_revision_id": str(run.tender_revision_id),
            "source_type": ResultSourceType.OPTIMIZER,
            "optimization_run_id": str(run.pk),
            "rank": rank,
        },
    )
    return result, None


def _store_rejections(run, rejections):
    rows = []
    seen = set()
    for rejection in rejections[:100]:
        identifier = rejection["candidate_identifier"]
        if identifier in seen:
            continue
        seen.add(identifier)
        rows.append(
            OptimizationCandidateRejection(
                optimization_run=run,
                candidate_identifier=identifier,
                reason_code=rejection["reason_code"],
                safe_detail=rejection["safe_detail"],
            )
        )
    OptimizationCandidateRejection.objects.bulk_create(
        rows, ignore_conflicts=True
    )


def complete_optimization_run(*, run_id, outcome, correlation_id):
    with transaction.atomic():
        run = OptimizationRun.objects.select_for_update().select_related(
            "tender_revision__tender_request", "requested_by"
        ).get(pk=run_id)
        if run.is_terminal:
            return run
        if run.status != OptimizationStatus.RUNNING:
            raise InvalidTransition("Optimization run belum berjalan.")
        if canonical_hash(run.input_snapshot) != run.input_hash:
            raise ValueError("Hash snapshot optimization tidak valid.")
        parsed = parse_optimization_input_snapshot(run.input_snapshot)
        captured_at = timezone.now()
        stored_rejections = [
            {
                "candidate_identifier": item.candidate_identifier,
                "reason_code": item.reason_code,
                "safe_detail": item.safe_detail,
            }
            for item in outcome.rejections
        ]
        result_count = 0
        for candidate in outcome.candidates:
            result, rejection = _persist_candidate(
                run=run,
                candidate=candidate,
                parsed=parsed,
                rank=result_count + 1,
                captured_at=captured_at,
            )
            if result is not None:
                result_count += 1
            elif rejection is not None:
                stored_rejections.append(rejection)
        _store_rejections(run, stored_rejections)
        previous_status = run.status
        run.status = OptimizationStatus.COMPLETED
        run.result_count = result_count
        run.completed_at = captured_at
        run.version += 1
        run.full_clean(validate_unique=False)
        run.save(
            update_fields=[
                "status",
                "result_count",
                "completed_at",
                "version",
            ]
        )
        event = _write_run_event(
            run=run,
            action=OptimizationAuditAction.COMPLETED,
            correlation_id=correlation_id,
            from_status=previous_status,
            to_status=run.status,
        )
        create_notification(
            recipient=run.requested_by,
            notification_type=NotificationType.OPTIMIZATION_COMPLETED,
            source_event_id=event.pk,
            source_entity_type="OptimizationRun",
            source_entity_id=run.pk,
            title="Optimization selesai",
            message=(
                f"Optimization {run.tender_request.internal_code} selesai "
                f"dengan {result_count} rekomendasi."
            ),
        )
        return run


def fail_optimization_run(
    *,
    run_id,
    safe_error_code,
    safe_error_message,
    diagnostic_reference,
    correlation_id,
):
    with transaction.atomic():
        run = OptimizationRun.objects.select_for_update().select_related(
            "tender_request", "requested_by"
        ).get(pk=run_id)
        if run.is_terminal:
            return run
        if run.status != OptimizationStatus.RUNNING:
            raise InvalidTransition("Optimization run belum berjalan.")
        previous_status = run.status
        run.status = OptimizationStatus.FAILED
        run.safe_error_code = str(safe_error_code)[:64]
        run.safe_error_message = str(safe_error_message)[:2000]
        run.diagnostic_reference = str(diagnostic_reference)[:100]
        run.completed_at = timezone.now()
        run.version += 1
        run.full_clean(validate_unique=False)
        run.save(
            update_fields=[
                "status",
                "safe_error_code",
                "safe_error_message",
                "diagnostic_reference",
                "completed_at",
                "version",
            ]
        )
        event = _write_run_event(
            run=run,
            action=OptimizationAuditAction.FAILED,
            correlation_id=correlation_id,
            from_status=previous_status,
            to_status=run.status,
        )
        create_notification(
            recipient=run.requested_by,
            notification_type=NotificationType.OPTIMIZATION_FAILED,
            source_event_id=event.pk,
            source_entity_type="OptimizationRun",
            source_entity_id=run.pk,
            title="Optimization gagal",
            message=(
                f"Optimization {run.tender_request.internal_code} gagal. "
                f"Referensi: {run.diagnostic_reference}."
            ),
        )
        return run


def calculate_run_outcome(*, run, should_stop=None):
    if canonical_hash(run.input_snapshot) != run.input_hash:
        raise ValueError("Hash snapshot optimization tidak valid.")
    parsed = parse_optimization_input_snapshot(run.input_snapshot)
    return optimize(
        parsed["items"],
        max_results=settings.OPTIMIZER_MAX_RESULTS,
        exploration_limit=settings.OPTIMIZER_EXPLORATION_LIMIT,
        should_stop=should_stop,
    )
