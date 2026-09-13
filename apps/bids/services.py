"""Transactional services for Bid Proposal and pricing."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.policies import require_procurement_staff
from apps.audit.writer import write_audit_event
from apps.core.domain.canonical_json import canonical_hash
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.sourcing.choices import ResultStatus
from apps.sourcing.models import ProcurementResultSelection
from apps.tender.models import TenderRequest

from .calculations import CALCULATION_VERSION, calculate_bid_pricing
from .choices import BidAuditAction, BidStatus
from .models import BidProposal, BidProposalItem, BidProposalRevision
from .snapshots import SNAPSHOT_SCHEMA_VERSION, build_submission_snapshot


def _write_event(
    *,
    actor,
    proposal,
    revision,
    action,
    correlation_id,
    from_status=None,
    to_status=None,
    metadata=None,
):
    details = {
        "bid_proposal_id": str(proposal.pk),
        "proposal_number": proposal.proposal_number,
        "revision_number": revision.revision_number,
        "tender_request_id": str(proposal.tender_request_id),
    }
    details.update(metadata or {})
    return write_audit_event(
        actor=actor,
        entity_type="BidProposalRevision",
        entity_id=revision.pk,
        entity_revision=revision.version,
        action=action,
        correlation_id=correlation_id,
        from_status=from_status,
        to_status=to_status,
        metadata=details,
    )


def _current_selection(tender):
    selection = (
        ProcurementResultSelection.objects.select_related(
            "procurement_result", "tender_revision"
        )
        .filter(tender_request=tender)
        .first()
    )
    if selection is None:
        raise InvalidTransition(
            "Pilih Procurement Result VALID sebelum membuat Bid."
        )
    result = selection.procurement_result
    if (
        result.status != ResultStatus.VALID
        or result.tender_revision_id != selection.tender_revision_id
        or selection.tender_revision.tender_request_id != tender.pk
    ):
        raise InvalidTransition(
            "Procurement Result terpilih tidak valid untuk Tender ini."
        )
    if selection.tender_revision.revision_number != (
        tender.current_revision_number
    ):
        raise InvalidTransition(
            "Pilih result dari revision Tender terbaru."
        )
    if canonical_hash(result.result_snapshot) != result.result_hash:
        raise InvalidTransition("Hash Procurement Result tidak valid.")
    return selection


def _new_proposal_number():
    year = timezone.localdate().year
    return f"BID-{year}-{uuid.uuid4().hex[:8].upper()}"


def create_bid_proposal(*, actor, tender_request_id, correlation_id):
    require_procurement_staff(actor)
    with transaction.atomic():
        try:
            tender = TenderRequest.objects.select_for_update().get(
                pk=tender_request_id
            )
        except TenderRequest.DoesNotExist as error:
            raise ValidationError("Tender tidak ditemukan.") from error
        selection = _current_selection(tender)
        result = selection.procurement_result
        proposal = BidProposal.objects.create(
            proposal_number=_new_proposal_number(),
            tender_request=tender,
            created_by=actor,
        )
        revision = BidProposalRevision(
            bid_proposal=proposal,
            revision_number=1,
            tender_revision=selection.tender_revision,
            selected_result=result,
            status=BidStatus.DRAFT,
            total_purchase=result.total_purchase,
            currency=result.currency,
            calculation_version=CALCULATION_VERSION,
            snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
            selected_result_snapshot=result.result_snapshot,
            created_by=actor,
        )
        revision.full_clean()
        revision.save()
        _write_event(
            actor=actor,
            proposal=proposal,
            revision=revision,
            action=BidAuditAction.CREATED,
            correlation_id=correlation_id,
            to_status=BidStatus.DRAFT,
            metadata={"selection_id": str(selection.pk)},
        )
        return proposal, revision


def _locked_draft(*, revision_id, expected_version):
    try:
        revision = (
            BidProposalRevision.objects.select_for_update()
            .select_related(
                "bid_proposal__tender_request", "selected_result"
            )
            .get(pk=revision_id)
        )
    except BidProposalRevision.DoesNotExist as error:
        raise ValidationError("Bid revision tidak ditemukan.") from error
    if revision.status != BidStatus.DRAFT:
        raise InvalidTransition("Hanya Bid DRAFT yang dapat diubah.")
    if revision.version != expected_version:
        raise ConcurrencyConflict("Bid telah berubah. Muat ulang halaman.")
    if (
        revision.bid_proposal.current_revision_number
        != revision.revision_number
    ):
        raise InvalidTransition(
            "Hanya revision Bid terbaru yang dapat diubah."
        )
    return revision


def _snapshot_pricing_items(revision):
    try:
        items = revision.selected_result_snapshot["data"]["items"]
    except (KeyError, TypeError) as error:
        raise ValidationError(
            "Snapshot Procurement Result tidak lengkap."
        ) from error
    return [
        {
            "tender_item_id": item["tender_item_id"],
            "requested_quantity": Decimal(item["requested_quantity"]),
            "item_purchase_total": Decimal(item["item_purchase_total"]),
            "line_number": int(item["line_number"]),
            "product": item["product"],
            "unit": item["unit"],
        }
        for item in items
    ]


def _snapshot_hps(revision):
    raw_hps = revision.selected_result_snapshot["tender"].get("total_hps")
    return Decimal(raw_hps) if raw_hps is not None else None


def _calculate_revision_pricing(revision, target_margin_percent):
    items = _snapshot_pricing_items(revision)
    pricing = calculate_bid_pricing(
        items=items,
        target_margin_percent=target_margin_percent,
        total_hps=_snapshot_hps(revision),
    )
    if pricing.total_purchase != revision.total_purchase:
        raise ValidationError(
            "Total purchase snapshot tidak cocok dengan Bid."
        )
    return items, pricing


def set_target_margin(
    *, actor, revision_id, expected_version, target_margin_percent,
    correlation_id
):
    require_procurement_staff(actor)
    with transaction.atomic():
        revision = _locked_draft(
            revision_id=revision_id, expected_version=expected_version
        )
        try:
            snapshot_items, pricing = _calculate_revision_pricing(
                revision, target_margin_percent
            )
        except (ValueError, KeyError, TypeError) as error:
            raise ValidationError(str(error)) from error
        revision.items.all().delete()
        pricing_map = {
            item.tender_item_id: item for item in pricing.items
        }
        for item in snapshot_items:
            priced = pricing_map[str(item["tender_item_id"])]
            BidProposalItem.objects.create(
                bid_revision=revision,
                tender_request_item_id=item["tender_item_id"],
                line_number=item["line_number"],
                product_snapshot=item["product"],
                requested_quantity=item["requested_quantity"],
                unit=item["unit"],
                item_purchase_total=priced.item_purchase_total,
                unit_purchase_cost=priced.unit_purchase_cost,
                bid_unit_price=priced.bid_unit_price,
                item_bid_total=priced.item_bid_total,
                currency=revision.currency,
            )
        revision.target_margin_percent = pricing.target_margin_percent
        revision.total_bid_value = pricing.total_bid_value
        revision.gross_profit = pricing.gross_profit
        revision.actual_margin_percent = pricing.actual_margin_percent
        revision.max_margin_percent = pricing.max_margin_percent
        revision.is_hps_feasible = pricing.is_hps_feasible
        revision.version += 1
        revision.full_clean()
        revision.save(
            update_fields=[
                "target_margin_percent",
                "total_bid_value",
                "gross_profit",
                "actual_margin_percent",
                "max_margin_percent",
                "is_hps_feasible",
                "version",
                "updated_at",
            ]
        )
        _write_event(
            actor=actor,
            proposal=revision.bid_proposal,
            revision=revision,
            action=BidAuditAction.PRICED,
            correlation_id=correlation_id,
            from_status=BidStatus.DRAFT,
            to_status=BidStatus.DRAFT,
        )
        return revision


def _assert_submission_valid(revision):
    selection = _current_selection(revision.bid_proposal.tender_request)
    if selection.procurement_result_id != revision.selected_result_id:
        raise InvalidTransition(
            "Procurement Result terpilih telah berubah. Buat Bid baru."
        )
    result = revision.selected_result
    if (
        result.status != ResultStatus.VALID
        or canonical_hash(result.result_snapshot) != result.result_hash
        or result.result_hash
        != canonical_hash(revision.selected_result_snapshot)
    ):
        raise InvalidTransition("Procurement Result Bid tidak lagi valid.")
    if revision.target_margin_percent is None:
        raise InvalidTransition(
            "Tetapkan target margin sebelum submission."
        )
    try:
        _items, pricing = _calculate_revision_pricing(
            revision, revision.target_margin_percent
        )
    except ValueError as error:
        raise InvalidTransition(str(error)) from error
    stored_totals = (
        revision.total_bid_value,
        revision.gross_profit,
        revision.actual_margin_percent,
        revision.max_margin_percent,
        revision.is_hps_feasible,
    )
    calculated_totals = (
        pricing.total_bid_value,
        pricing.gross_profit,
        pricing.actual_margin_percent,
        pricing.max_margin_percent,
        pricing.is_hps_feasible,
    )
    snapshot_items = _snapshot_pricing_items(revision)
    snapshot_map = {
        str(item["tender_item_id"]): item for item in snapshot_items
    }
    pricing_map = {
        item.tender_item_id: item for item in pricing.items
    }
    stored_items = list(revision.items.all())
    item_values_match = len(stored_items) == len(pricing.items)
    for item in stored_items:
        item_id = str(item.tender_request_item_id)
        raw = snapshot_map.get(item_id)
        calculated = pricing_map.get(item_id)
        if raw is None or calculated is None:
            item_values_match = False
            break
        if (
            item.line_number != raw["line_number"]
            or item.product_snapshot != raw["product"]
            or item.requested_quantity != raw["requested_quantity"]
            or item.unit != raw["unit"]
            or item.item_purchase_total
            != calculated.item_purchase_total
            or item.unit_purchase_cost
            != calculated.unit_purchase_cost
            or item.bid_unit_price != calculated.bid_unit_price
            or item.item_bid_total != calculated.item_bid_total
            or item.currency != revision.currency
        ):
            item_values_match = False
            break
    if stored_totals != calculated_totals or not item_values_match:
        raise InvalidTransition("Pricing Bid tidak konsisten.")
    if revision.is_hps_feasible is False:
        raise InvalidTransition("Nilai Bid melebihi HPS Tender.")


def submit_bid(
    *, actor, revision_id, expected_version, correlation_id
):
    require_procurement_staff(actor)
    with transaction.atomic():
        revision = _locked_draft(
            revision_id=revision_id, expected_version=expected_version
        )
        list(revision.items.select_for_update())
        _assert_submission_valid(revision)
        captured_at = timezone.now()
        previous_status = revision.status
        revision.status = BidStatus.WAITING_APPROVAL
        revision.submitted_by = actor
        revision.submitted_at = captured_at
        revision.version += 1
        snapshot = build_submission_snapshot(
            revision=revision, captured_at=captured_at
        )
        revision.submission_snapshot = snapshot
        revision.submission_hash = canonical_hash(snapshot)
        revision.full_clean()
        revision.save(
            update_fields=[
                "status",
                "submitted_by",
                "submitted_at",
                "submission_snapshot",
                "submission_hash",
                "version",
                "updated_at",
            ]
        )
        _write_event(
            actor=actor,
            proposal=revision.bid_proposal,
            revision=revision,
            action=BidAuditAction.SUBMITTED,
            correlation_id=correlation_id,
            from_status=previous_status,
            to_status=revision.status,
        )
        return revision


def revise_rejected_bid(
    *, actor, proposal_id, expected_version, correlation_id
):
    require_procurement_staff(actor)
    with transaction.atomic():
        try:
            proposal = (
                BidProposal.objects.select_for_update()
                .select_related("tender_request")
                .get(pk=proposal_id)
            )
        except BidProposal.DoesNotExist as error:
            raise ValidationError(
                "Bid Proposal tidak ditemukan."
            ) from error
        if proposal.version != expected_version:
            raise ConcurrencyConflict(
                "Bid telah berubah. Muat ulang halaman."
            )
        previous = proposal.revisions.select_for_update().get(
            revision_number=proposal.current_revision_number
        )
        if previous.status != BidStatus.REJECTED:
            raise InvalidTransition(
                "Hanya Bid yang ditolak yang dapat direvisi."
            )
        selection = _current_selection(proposal.tender_request)
        result = selection.procurement_result
        next_number = proposal.current_revision_number + 1
        revision = BidProposalRevision(
            bid_proposal=proposal,
            revision_number=next_number,
            tender_revision=selection.tender_revision,
            selected_result=result,
            status=BidStatus.DRAFT,
            total_purchase=result.total_purchase,
            currency=result.currency,
            calculation_version=CALCULATION_VERSION,
            snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
            selected_result_snapshot=result.result_snapshot,
            created_by=actor,
        )
        revision.full_clean()
        revision.save()
        proposal.current_revision_number = next_number
        proposal.version += 1
        proposal.save(
            update_fields=[
                "current_revision_number",
                "version",
                "updated_at",
            ]
        )
        _write_event(
            actor=actor,
            proposal=proposal,
            revision=revision,
            action=BidAuditAction.REVISION_CREATED,
            correlation_id=correlation_id,
            to_status=BidStatus.DRAFT,
            metadata={"previous_revision_id": str(previous.pk)},
        )
        return revision
