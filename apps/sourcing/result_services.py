"""Transactional application services for Procurement Result."""

from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.accounts.policies import require_procurement_staff
from apps.audit.writer import write_audit_event
from apps.core.domain.canonical_json import canonical_hash
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.tender.models import (
    TenderRequest,
    TenderRequestRevision,
)

from .calculations import (
    CALCULATION_VERSION,
    calculate_allocation_purchase,
    normalize_quantity,
)
from .choices import ResultAuditAction, ResultSourceType, ResultStatus
from .models import (
    ProcurementResult,
    ProcurementResultItem,
    ProcurementResultSelection,
    SupplierAllocation,
    SupplierOffer,
)
from .policies import evaluate_offer_eligibility
from .selectors import offer_eligibility_input
from .snapshots import (
    SNAPSHOT_SCHEMA_VERSION,
    build_offer_snapshot,
    build_procurement_result_snapshot,
    build_supplier_snapshot,
    decimal_string,
)
from .validators import (
    AllocationInput,
    RequirementInput,
    ResultItemInput,
    validate_result_candidate,
)


def _write_result_event(
    *,
    actor,
    result,
    action,
    correlation_id,
    from_status=None,
    to_status=None,
):
    return write_audit_event(
        actor=actor,
        entity_type="ProcurementResult",
        entity_id=result.pk,
        entity_revision=result.version,
        action=action,
        correlation_id=correlation_id,
        from_status=from_status,
        to_status=to_status,
        metadata={
            "tender_revision_id": str(result.tender_revision_id),
            "source_type": result.source_type,
        },
    )


def _get_revision(revision_id):
    try:
        return TenderRequestRevision.objects.select_related(
            "tender_request"
        ).prefetch_related("items").get(pk=revision_id)
    except TenderRequestRevision.DoesNotExist as error:
        raise ValidationError(
            {"tender_revision": "Revision tender tidak ditemukan."}
        ) from error


def _normalize_allocations(revision, allocations, evaluation_date):
    raw_allocations = list(allocations or ())
    item_map = {
        str(item.pk): item
        for item in revision.items.select_related("product")
    }
    offer_ids = {raw.get("supplier_offer_id") for raw in raw_allocations}
    offer_map = {
        str(offer.pk): offer
        for offer in SupplierOffer.objects.select_related(
            "supplier", "product"
        ).filter(pk__in=offer_ids)
    }
    normalized = []
    seen_lines = set()
    seen_offers = set()
    offer_totals = defaultdict(lambda: Decimal("0.000"))

    for raw in raw_allocations:
        item_id = str(raw.get("tender_item_id") or "")
        offer_id = str(raw.get("supplier_offer_id") or "")
        item = item_map.get(item_id)
        offer = offer_map.get(offer_id)
        if item is None:
            raise ValidationError(
                {"allocations": "Item bukan milik revision tender."}
            )
        if offer is None:
            raise ValidationError(
                {"allocations": "Supplier offer tidak ditemukan."}
            )
        try:
            line_number = int(raw["line_number"])
            quantity = normalize_quantity(raw["allocated_quantity"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError(
                {
                    "allocations": (
                        "Baris dan quantity allocation tidak valid."
                    )
                }
            ) from error
        if line_number <= 0 or quantity <= 0:
            raise ValidationError(
                {
                    "allocations": (
                        "Baris dan quantity allocation harus lebih "
                        "dari nol."
                    )
                }
            )
        line_key = (item_id, line_number)
        offer_key = (item_id, offer_id)
        if line_key in seen_lines or offer_key in seen_offers:
            raise ValidationError(
                {
                    "allocations": (
                        "Baris dan offer harus unik pada setiap "
                        "item tender."
                    )
                }
            )
        seen_lines.add(line_key)
        seen_offers.add(offer_key)
        eligibility = offer_eligibility_input(offer)
        decision = evaluate_offer_eligibility(
            eligibility,
            as_of_date=evaluation_date,
            product_id=item.product_id,
        )
        if not decision.eligible:
            raise ValidationError(
                {
                    "allocations": (
                        f"Offer pada item {item.line_number}: "
                        f"{decision.message}"
                    )
                }
            )
        offer_totals[offer_id] += quantity
        normalized.append(
            {
                "item": item,
                "offer": offer,
                "line_number": line_number,
                "allocated_quantity": quantity,
            }
        )

    for offer_id, quantity in offer_totals.items():
        limit = offer_map[offer_id].available_quantity
        if limit is not None and quantity > normalize_quantity(limit):
            raise ValidationError(
                {
                    "allocations": (
                        "Total allocation untuk satu offer melebihi "
                        "jumlah tersedia."
                    )
                }
            )
    return sorted(
        normalized,
        key=lambda value: (
            value["item"].line_number,
            value["line_number"],
        ),
    )


def _replace_children(result, normalized_allocations):
    result.items.all().delete()
    grouped = defaultdict(list)
    for allocation in normalized_allocations:
        grouped[allocation["item"].pk].append(allocation)

    for group in grouped.values():
        tender_item = group[0]["item"]
        result_item = ProcurementResultItem(
            procurement_result=result,
            tender_request_item=tender_item,
            line_number=tender_item.line_number,
            requested_quantity_snapshot=tender_item.requested_quantity,
            unit_snapshot=tender_item.unit,
            item_purchase_total=None,
            currency="IDR",
            product_snapshot=tender_item.product_snapshot,
        )
        result_item.full_clean()
        result_item.save()
        for value in group:
            offer = value["offer"]
            allocation = SupplierAllocation(
                procurement_result_item=result_item,
                supplier_offer=offer,
                line_number=value["line_number"],
                allocated_quantity=value["allocated_quantity"],
                base_unit_price_snapshot=offer.base_unit_price,
                discount_percent_snapshot=offer.discount_percent,
                net_purchase_price_snapshot=offer.net_purchase_price,
                allocation_purchase=calculate_allocation_purchase(
                    value["allocated_quantity"],
                    offer.net_purchase_price,
                ),
                currency=offer.currency,
                supplier_snapshot=build_supplier_snapshot(offer.supplier),
                offer_snapshot=build_offer_snapshot(offer),
            )
            allocation.full_clean()
            allocation.save()


def create_manual_result(
    *, actor, tender_revision_id, allocations, correlation_id
):
    require_procurement_staff(actor)
    evaluation_date = timezone.localdate()
    with transaction.atomic():
        revision = _get_revision(tender_revision_id)
        normalized = _normalize_allocations(
            revision, allocations, evaluation_date
        )
        result = ProcurementResult(
            tender_revision=revision,
            source_type=ResultSourceType.MANUAL,
            status=ResultStatus.DRAFT,
            currency="IDR",
            calculation_version=CALCULATION_VERSION,
            created_by=actor,
        )
        result.full_clean()
        result.save()
        _replace_children(result, normalized)
        _write_result_event(
            actor=actor,
            result=result,
            action=ResultAuditAction.RESULT_CREATED,
            correlation_id=correlation_id,
            to_status=ResultStatus.DRAFT,
        )
        return result


def _locked_draft(result_id, expected_version):
    try:
        result = (
            ProcurementResult.objects.select_for_update()
            .select_related("tender_revision__tender_request")
            .get(pk=result_id)
        )
    except ProcurementResult.DoesNotExist as error:
        raise ValidationError(
            "Procurement Result tidak ditemukan."
        ) from error
    if result.status != ResultStatus.DRAFT:
        raise InvalidTransition(
            "Hanya Procurement Result DRAFT yang dapat diubah."
        )
    if result.version != expected_version:
        raise ConcurrencyConflict(
            "Procurement Result telah berubah. Muat ulang halaman."
        )
    return result


def update_draft_result(
    *, actor, result_id, expected_version, allocations, correlation_id
):
    require_procurement_staff(actor)
    evaluation_date = timezone.localdate()
    with transaction.atomic():
        result = _locked_draft(result_id, expected_version)
        revision = _get_revision(result.tender_revision_id)
        normalized = _normalize_allocations(
            revision, allocations, evaluation_date
        )
        _replace_children(result, normalized)
        result.version += 1
        result.save(update_fields=["version", "updated_at"])
        _write_result_event(
            actor=actor,
            result=result,
            action=ResultAuditAction.RESULT_UPDATED,
            correlation_id=correlation_id,
            from_status=ResultStatus.DRAFT,
            to_status=ResultStatus.DRAFT,
        )
        return result


def _load_result_input(result):
    requirements = [
        RequirementInput(
            tender_item_id=str(item.pk),
            line_number=item.line_number,
            product_id=str(item.product_id),
            requested_quantity=item.requested_quantity,
            unit=item.unit,
            product_snapshot=item.product_snapshot,
        )
        for item in result.tender_revision.items.all()
    ]
    result_items = []
    stored_items = ProcurementResultItem.objects.filter(
        procurement_result=result
    ).select_related("tender_request_item").prefetch_related(
        Prefetch(
            "allocations",
            queryset=SupplierAllocation.objects.select_related(
                "supplier_offer__supplier", "supplier_offer__product"
            ),
        )
    )
    for item in stored_items:
        allocations = tuple(
            AllocationInput(
                line_number=allocation.line_number,
                offer_id=str(allocation.supplier_offer_id),
                product_id=str(allocation.supplier_offer.product_id),
                allocated_quantity=allocation.allocated_quantity,
                base_unit_price=allocation.base_unit_price_snapshot,
                discount_percent=allocation.discount_percent_snapshot,
                net_purchase_price=allocation.net_purchase_price_snapshot,
                currency=allocation.currency,
                eligibility=offer_eligibility_input(
                    allocation.supplier_offer
                ),
            )
            for allocation in item.allocations.all()
        )
        result_items.append(
            ResultItemInput(
                tender_item_id=str(item.tender_request_item_id),
                line_number=item.line_number,
                requested_quantity=item.requested_quantity_snapshot,
                unit=item.unit_snapshot,
                product_snapshot=item.product_snapshot,
                allocations=allocations,
            )
        )
    return requirements, result_items, list(stored_items)


def _snapshot_items(stored_items):
    items = []
    for item in stored_items:
        allocations = []
        for allocation in item.allocations.all():
            allocations.append(
                {
                    "allocation_id": str(allocation.pk),
                    "line_number": allocation.line_number,
                    "offer_id": str(allocation.supplier_offer_id),
                    "supplier": allocation.supplier_snapshot,
                    "offer": allocation.offer_snapshot,
                    "allocated_quantity": decimal_string(
                        allocation.allocated_quantity, "0.001"
                    ),
                    "base_unit_price": decimal_string(
                        allocation.base_unit_price_snapshot, "0.0001"
                    ),
                    "discount_percent": decimal_string(
                        allocation.discount_percent_snapshot, "0.0001"
                    ),
                    "net_purchase_price": decimal_string(
                        allocation.net_purchase_price_snapshot, "0.0001"
                    ),
                    "allocation_purchase": decimal_string(
                        allocation.allocation_purchase, "0.01"
                    ),
                    "currency": allocation.currency,
                }
            )
        items.append(
            {
                "result_item_id": str(item.pk),
                "tender_item_id": str(item.tender_request_item_id),
                "line_number": item.line_number,
                "product": item.product_snapshot,
                "requested_quantity": decimal_string(
                    item.requested_quantity_snapshot, "0.001"
                ),
                "unit": item.unit_snapshot,
                "item_purchase_total": decimal_string(
                    item.item_purchase_total, "0.01"
                ),
                "currency": item.currency,
                "allocations": allocations,
            }
        )
    return items


def validate_result(
    *, actor, result_id, expected_version, correlation_id
):
    require_procurement_staff(actor)
    with transaction.atomic():
        result = _locked_draft(result_id, expected_version)
        result.tender_revision = (
            TenderRequestRevision.objects.select_related(
                "tender_request"
            ).prefetch_related("items").get(pk=result.tender_revision_id)
        )
        requirements, result_items, stored_items = _load_result_input(
            result
        )
        outcome = validate_result_candidate(
            requirements=requirements,
            result_items=result_items,
            as_of_date=timezone.localdate(),
        )
        if not outcome.is_valid:
            messages = [
                f"{item.code}: {item.message}"
                for item in outcome.violations
            ]
            raise ValidationError({"allocations": messages})

        allocation_amounts = {
            (item.tender_item_id, item.allocation_line): item.purchase
            for item in outcome.allocation_amounts
        }
        item_amounts = {
            item.tender_item_id: item.purchase
            for item in outcome.item_amounts
        }
        for item in stored_items:
            tender_item_id = str(item.tender_request_item_id)
            item.item_purchase_total = item_amounts[tender_item_id]
            item.save(update_fields=["item_purchase_total", "updated_at"])
            for allocation in item.allocations.all():
                allocation.allocation_purchase = allocation_amounts[
                    (tender_item_id, allocation.line_number)
                ]
                allocation.save(
                    update_fields=["allocation_purchase", "updated_at"]
                )

        captured_at = timezone.now()
        result.total_purchase = outcome.total_purchase
        result.snapshot_schema_version = SNAPSHOT_SCHEMA_VERSION
        result.validated_at = captured_at
        result.status = ResultStatus.VALID
        result.version += 1
        snapshot = build_procurement_result_snapshot(
            result=result,
            tender_revision=result.tender_revision,
            items=_snapshot_items(stored_items),
            captured_at=captured_at,
        )
        result.result_snapshot = snapshot
        result.result_hash = canonical_hash(snapshot)
        result.full_clean()
        result.save(
            update_fields=[
                "total_purchase",
                "snapshot_schema_version",
                "result_snapshot",
                "result_hash",
                "validated_at",
                "status",
                "version",
                "updated_at",
            ]
        )
        _write_result_event(
            actor=actor,
            result=result,
            action=ResultAuditAction.RESULT_VALIDATED,
            correlation_id=correlation_id,
            from_status=ResultStatus.DRAFT,
            to_status=ResultStatus.VALID,
        )
        return result


def customize_result(*, actor, source_result_id, correlation_id):
    require_procurement_staff(actor)
    with transaction.atomic():
        try:
            source = ProcurementResult.objects.select_for_update().get(
                pk=source_result_id,
                status=ResultStatus.VALID,
            )
        except ProcurementResult.DoesNotExist as error:
            raise InvalidTransition(
                "Hanya Procurement Result VALID yang dapat dikustomisasi."
            ) from error
        source_items = ProcurementResultItem.objects.filter(
            procurement_result=source
        ).prefetch_related("allocations")
        customized = ProcurementResult.objects.create(
            tender_revision=source.tender_revision,
            source_type=ResultSourceType.CUSTOMIZED,
            status=ResultStatus.DRAFT,
            source_result=source,
            currency=source.currency,
            calculation_version=source.calculation_version,
            created_by=actor,
        )
        for source_item in source_items:
            item = ProcurementResultItem.objects.create(
                procurement_result=customized,
                tender_request_item=source_item.tender_request_item,
                line_number=source_item.line_number,
                requested_quantity_snapshot=(
                    source_item.requested_quantity_snapshot
                ),
                unit_snapshot=source_item.unit_snapshot,
                item_purchase_total=None,
                currency=source_item.currency,
                product_snapshot=source_item.product_snapshot,
            )
            for source_allocation in source_item.allocations.all():
                SupplierAllocation.objects.create(
                    procurement_result_item=item,
                    supplier_offer=source_allocation.supplier_offer,
                    line_number=source_allocation.line_number,
                    allocated_quantity=source_allocation.allocated_quantity,
                    base_unit_price_snapshot=(
                        source_allocation.base_unit_price_snapshot
                    ),
                    discount_percent_snapshot=(
                        source_allocation.discount_percent_snapshot
                    ),
                    net_purchase_price_snapshot=(
                        source_allocation.net_purchase_price_snapshot
                    ),
                    allocation_purchase=(
                        source_allocation.allocation_purchase
                    ),
                    currency=source_allocation.currency,
                    supplier_snapshot=source_allocation.supplier_snapshot,
                    offer_snapshot=source_allocation.offer_snapshot,
                )
        _write_result_event(
            actor=actor,
            result=customized,
            action=ResultAuditAction.RESULT_CUSTOMIZED,
            correlation_id=correlation_id,
            to_status=ResultStatus.DRAFT,
        )
        return customized


def select_result(*, actor, result_id, correlation_id):
    require_procurement_staff(actor)
    with transaction.atomic():
        try:
            result = ProcurementResult.objects.select_related(
                "tender_revision__tender_request"
            ).get(pk=result_id)
        except ProcurementResult.DoesNotExist as error:
            raise ValidationError(
                "Procurement Result tidak ditemukan."
            ) from error
        if result.status != ResultStatus.VALID:
            raise InvalidTransition(
                "Hanya Procurement Result VALID yang dapat dipilih."
            )
        tender = TenderRequest.objects.select_for_update().get(
            pk=result.tender_revision.tender_request_id
        )
        latest = ProcurementResultSelection.objects.filter(
            tender_request=tender
        ).first()
        if latest and latest.procurement_result_id == result.pk:
            return latest
        selection = ProcurementResultSelection(
            tender_request=tender,
            tender_revision=result.tender_revision,
            procurement_result=result,
            selection_number=(
                latest.selection_number + 1 if latest else 1
            ),
            selected_by=actor,
        )
        selection.full_clean()
        selection.save()
        write_audit_event(
            actor=actor,
            entity_type="ProcurementResult",
            entity_id=result.pk,
            entity_revision=result.version,
            action=ResultAuditAction.RESULT_SELECTED,
            correlation_id=correlation_id,
            metadata={
                "selection_id": str(selection.pk),
                "selection_number": selection.selection_number,
                "tender_request_id": str(tender.pk),
                "tender_revision_id": str(result.tender_revision_id),
            },
        )
        return selection
