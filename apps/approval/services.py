"""Transactional Manager decisions for submitted Bid revisions."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.policies import require_manager
from apps.audit.writer import write_audit_event
from apps.bids.choices import BidStatus
from apps.bids.models import BidProposalRevision
from apps.core.domain.canonical_json import canonical_hash
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.notifications.choices import NotificationType
from apps.notifications.services import create_notification

from .choices import ApprovalAuditAction, ApprovalDecisionType
from .models import ApprovalDecision


def _locked_submission(*, revision_id, expected_version):
    try:
        revision = (
            BidProposalRevision.objects.select_for_update(of=("self",))
            .select_related(
                "bid_proposal__tender_request",
                "selected_result",
                "submitted_by",
            )
            .get(pk=revision_id)
        )
    except BidProposalRevision.DoesNotExist as error:
        raise ValidationError("Bid revision tidak ditemukan.") from error
    if revision.status != BidStatus.WAITING_APPROVAL:
        raise InvalidTransition(
            "Bid tidak lagi menunggu keputusan Manager."
        )
    if revision.version != expected_version:
        raise ConcurrencyConflict("Bid telah berubah. Muat ulang halaman.")
    if (
        revision.bid_proposal.current_revision_number
        != revision.revision_number
    ):
        raise InvalidTransition(
            "Hanya revision Bid terbaru yang diproses."
        )
    if (
        not revision.submission_hash
        or canonical_hash(revision.submission_snapshot)
        != revision.submission_hash
    ):
        raise InvalidTransition("Snapshot submission Bid tidak valid.")
    return revision


def _decide(
    *, actor, revision_id, expected_version, decision, reason,
    correlation_id
):
    require_manager(actor)
    normalized_reason = str(reason or "").strip()
    if decision == ApprovalDecisionType.REJECTED and not normalized_reason:
        raise ValidationError({"reason": "Alasan penolakan wajib diisi."})
    with transaction.atomic():
        revision = _locked_submission(
            revision_id=revision_id, expected_version=expected_version
        )
        decided_at = timezone.now()
        approval = ApprovalDecision(
            bid_revision=revision,
            decision=decision,
            reason=(
                normalized_reason
                if decision == ApprovalDecisionType.REJECTED
                else None
            ),
            submission_hash=revision.submission_hash,
            decided_by=actor,
            decided_at=decided_at,
        )
        approval.full_clean()
        try:
            approval.save()
        except IntegrityError as error:
            raise ConcurrencyConflict(
                "Keputusan untuk Bid ini sudah dibuat."
            ) from error
        previous_status = revision.status
        revision.status = (
            BidStatus.APPROVED
            if decision == ApprovalDecisionType.APPROVED
            else BidStatus.REJECTED
        )
        revision.version += 1
        revision.full_clean()
        revision.save(update_fields=["status", "version", "updated_at"])
        action = (
            ApprovalAuditAction.APPROVED
            if decision == ApprovalDecisionType.APPROVED
            else ApprovalAuditAction.REJECTED
        )
        event = write_audit_event(
            actor=actor,
            entity_type="BidProposalRevision",
            entity_id=revision.pk,
            entity_revision=revision.version,
            action=action,
            correlation_id=correlation_id,
            from_status=previous_status,
            to_status=revision.status,
            reason=approval.reason,
            metadata={
                "bid_proposal_id": str(revision.bid_proposal_id),
                "proposal_number": revision.bid_proposal.proposal_number,
                "decision_id": str(approval.pk),
            },
        )
        if decision == ApprovalDecisionType.REJECTED:
            create_notification(
                recipient=revision.submitted_by,
                notification_type=NotificationType.BID_REJECTED,
                source_event_id=event.pk,
                source_entity_type="BidProposalRevision",
                source_entity_id=revision.pk,
                title="Bid Proposal ditolak",
                message=(
                    f"{revision.bid_proposal.proposal_number} ditolak: "
                    f"{normalized_reason}"
                ),
            )
        return approval


def approve_bid(
    *, actor, revision_id, expected_version, correlation_id
):
    return _decide(
        actor=actor,
        revision_id=revision_id,
        expected_version=expected_version,
        decision=ApprovalDecisionType.APPROVED,
        reason=None,
        correlation_id=correlation_id,
    )


def reject_bid(
    *, actor, revision_id, expected_version, reason, correlation_id
):
    return _decide(
        actor=actor,
        revision_id=revision_id,
        expected_version=expected_version,
        decision=ApprovalDecisionType.REJECTED,
        reason=reason,
        correlation_id=correlation_id,
    )
