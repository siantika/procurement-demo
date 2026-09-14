"""Lifecycle services for final document generation."""

import hashlib
import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.policies import require_procurement_staff
from apps.approval.choices import ApprovalDecisionType
from apps.audit.writer import write_audit_event
from apps.bids.choices import BidStatus
from apps.bids.models import BidProposalRevision
from apps.core.domain.canonical_json import canonical_hash
from apps.core.exceptions import InvalidTransition
from apps.notifications.choices import NotificationType
from apps.notifications.services import create_notification

from .choices import DocumentAuditAction, GenerationJobStatus
from .models import (
    DocumentGenerationJob,
    DocumentNumberSequence,
    FinalDocument,
)
from .snapshots import build_finalization_snapshot
from .storage import (
    PrivateStorageError,
    read_private_object,
    stat_private_object,
)

logger = logging.getLogger(__name__)


def publish_generation_job(job_id, correlation_id=None):
    from .tasks import execute_generation_job

    execute_generation_job.delay(
        str(job_id), str(correlation_id or job_id)
    )


def _publish_safely(job_id, correlation_id):
    try:
        publish_generation_job(job_id, correlation_id)
    except Exception:
        logger.exception(
            "Document task publish failed; reconciliation will retry",
            extra={"generation_job_id": str(job_id)},
        )


def _write_job_event(
    *, job, action, correlation_id, actor=None, from_status=None,
    to_status=None
):
    return write_audit_event(
        actor=actor,
        entity_type="DocumentGenerationJob",
        entity_id=job.pk,
        entity_revision=job.version,
        action=action,
        correlation_id=correlation_id,
        from_status=from_status,
        to_status=to_status,
        metadata={
            "bid_revision_id": str(job.bid_revision_id),
            "document_version": job.document_version,
        },
    )


def _next_document_number():
    year = timezone.localdate().year
    sequence, _created = DocumentNumberSequence.objects.get_or_create(
        year=year, defaults={"next_number": 1}
    )
    sequence = DocumentNumberSequence.objects.select_for_update().get(
        year=sequence.year
    )
    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])
    return f"BID/{year}/{number:06d}"


def _validate_signed_revision(revision):
    if revision.status not in {BidStatus.SIGNED, BidStatus.FINALIZED}:
        raise InvalidTransition(
            "Hanya Bid SIGNED yang dapat difinalisasi."
        )
    try:
        approval = revision.approval_decision
        signature = revision.signature
    except ObjectDoesNotExist as error:
        raise InvalidTransition(
            "Approval atau signature Bid tidak lengkap."
        ) from error
    if (
        approval.decision != ApprovalDecisionType.APPROVED
        or approval.submission_hash != revision.submission_hash
        or signature.approval_decision_id != approval.pk
        or signature.signed_by_id != approval.decided_by_id
        or signature.signed_snapshot_hash != revision.submission_hash
        or canonical_hash(revision.submission_snapshot)
        != revision.submission_hash
        or revision.is_hps_feasible is False
    ):
        raise InvalidTransition(
            "Approval, signature, atau submission Bid tidak valid."
        )
    return approval, signature


def request_finalization(*, actor, revision_id, correlation_id):
    require_procurement_staff(actor)
    with transaction.atomic():
        try:
            revision = (
                BidProposalRevision.objects.select_for_update(of=("self",))
                .select_related(
                    "bid_proposal",
                    "approval_decision__decided_by",
                    "signature__signed_by",
                )
                .get(pk=revision_id)
            )
        except BidProposalRevision.DoesNotExist as error:
            raise ValidationError(
                "Bid revision tidak ditemukan."
            ) from error
        approval, signature = _validate_signed_revision(revision)
        active_job = revision.generation_jobs.filter(
            status__in=(
                GenerationJobStatus.PENDING,
                GenerationJobStatus.RUNNING,
            )
        ).first()
        if active_job is not None:
            return active_job
        latest_version = (
            revision.generation_jobs.aggregate(
                value=Max("document_version")
            )["value"]
            or 0
        )
        document_version = latest_version + 1
        captured_at = timezone.now()
        template_version = settings.DOCUMENT_TEMPLATE_VERSION
        document_number = (
            f"{_next_document_number()}/R{revision.revision_number:02d}"
        )
        snapshot = build_finalization_snapshot(
            revision=revision,
            approval=approval,
            signature=signature,
            document_number=document_number,
            document_version=document_version,
            template_version=template_version,
            captured_at=captured_at,
        )
        job = DocumentGenerationJob(
            bid_revision=revision,
            document_version=document_version,
            template_version=template_version,
            snapshot_schema_version=(
                settings.DOCUMENT_SNAPSHOT_SCHEMA_VERSION
            ),
            input_snapshot=snapshot,
            input_hash=canonical_hash(snapshot),
            requested_by=actor,
        )
        job.full_clean(validate_unique=False)
        try:
            job.save()
        except IntegrityError as error:
            raise InvalidTransition(
                "Finalisasi untuk versi dokumen ini sudah diminta."
            ) from error
        _write_job_event(
            job=job,
            actor=actor,
            action=DocumentAuditAction.REQUESTED,
            correlation_id=correlation_id,
            to_status=job.status,
        )
        transaction.on_commit(
            lambda: _publish_safely(job.pk, correlation_id)
        )
        return job


def claim_generation_job(*, job_id, correlation_id):
    with transaction.atomic():
        try:
            job = DocumentGenerationJob.objects.select_for_update().get(
                pk=job_id
            )
        except DocumentGenerationJob.DoesNotExist:
            return None
        if job.status != GenerationJobStatus.PENDING:
            return None
        job.status = GenerationJobStatus.RUNNING
        job.started_at = timezone.now()
        job.attempt_count += 1
        job.version += 1
        job.full_clean(validate_unique=False)
        job.save(
            update_fields=[
                "status", "started_at", "attempt_count", "version"
            ]
        )
        return job


def release_generation_job_for_retry(*, job_id):
    with transaction.atomic():
        try:
            job = DocumentGenerationJob.objects.select_for_update().get(
                pk=job_id
            )
        except DocumentGenerationJob.DoesNotExist:
            return None
        if job.status != GenerationJobStatus.RUNNING:
            return None
        job.status = GenerationJobStatus.PENDING
        job.started_at = None
        job.version += 1
        job.full_clean(validate_unique=False)
        job.save(update_fields=["status", "started_at", "version"])
        return job


def complete_generation_job(
    *, job_id, object_key, object_version_id, size_bytes, sha256,
    correlation_id
):
    stored = stat_private_object(object_key)
    content = read_private_object(object_key)
    actual_hash = hashlib.sha256(content).hexdigest()
    if (
        stored.size != size_bytes
        or len(content) != size_bytes
        or actual_hash != sha256
        or stored.content_type != "application/pdf"
        or not content.startswith(b"%PDF-")
    ):
        raise ValidationError("Object PDF tidak lolos verifikasi.")
    with transaction.atomic():
        try:
            job = (
                DocumentGenerationJob.objects.select_for_update()
                .select_related("bid_revision", "requested_by")
                .get(pk=job_id)
            )
        except DocumentGenerationJob.DoesNotExist as error:
            raise ValidationError(
                "Generation job tidak ditemukan."
            ) from error
        if job.status == GenerationJobStatus.COMPLETED:
            return job.final_document
        if job.status != GenerationJobStatus.RUNNING:
            raise InvalidTransition(
                "Generation job tidak sedang diproses."
            )
        if canonical_hash(job.input_snapshot) != job.input_hash:
            raise InvalidTransition("Snapshot generation job tidak valid.")
        expected_key = (
            f"documents/{job.bid_revision_id}/"
            f"{job.bid_revision.revision_number}/"
            f"{job.document_version}/{job.pk}.pdf"
        )
        if object_key != expected_key:
            raise ValidationError("Object key PDF tidak valid.")
        revision = BidProposalRevision.objects.select_for_update().get(
            pk=job.bid_revision_id
        )
        if revision.status not in {
            BidStatus.SIGNED,
            BidStatus.FINALIZED,
        }:
            raise InvalidTransition("Status Bid tidak valid untuk PDF.")
        document = FinalDocument(
            generation_job=job,
            bid_revision=revision,
            document_version=job.document_version,
            document_number=job.input_snapshot["document"][
                "document_number"
            ],
            template_version=job.template_version,
            object_key=object_key,
            object_version_id=object_version_id or stored.version_id,
            size_bytes=size_bytes,
            sha256=sha256,
            snapshot_schema_version=job.snapshot_schema_version,
            content_snapshot=job.input_snapshot,
            finalized_by=job.requested_by,
        )
        document.full_clean(validate_unique=False)
        try:
            document.save()
        except IntegrityError:
            return FinalDocument.objects.get(generation_job=job)
        previous_job_status = job.status
        job.status = GenerationJobStatus.COMPLETED
        job.completed_at = timezone.now()
        job.safe_error_code = None
        job.safe_error_message = None
        job.diagnostic_reference = None
        job.version += 1
        job.full_clean(validate_unique=False)
        job.save(
            update_fields=[
                "status", "completed_at", "safe_error_code",
                "safe_error_message", "diagnostic_reference", "version"
            ]
        )
        previous_bid_status = revision.status
        if revision.status == BidStatus.SIGNED:
            revision.status = BidStatus.FINALIZED
            revision.version += 1
            revision.full_clean()
            revision.save(
                update_fields=["status", "version", "updated_at"]
            )
        event = _write_job_event(
            job=job,
            action=DocumentAuditAction.FINALIZED,
            correlation_id=correlation_id,
            from_status=previous_job_status,
            to_status=job.status,
        )
        create_notification(
            recipient=job.requested_by,
            notification_type=NotificationType.DOCUMENT_COMPLETED,
            source_event_id=event.pk,
            source_entity_type="DocumentGenerationJob",
            source_entity_id=job.pk,
            title="Dokumen final selesai",
            message=(
                f"{document.document_number} siap diunduh."
            ),
        )
        if previous_bid_status == BidStatus.SIGNED:
            write_audit_event(
                actor=None,
                entity_type="BidProposalRevision",
                entity_id=revision.pk,
                entity_revision=revision.version,
                action=DocumentAuditAction.FINALIZED,
                correlation_id=correlation_id,
                from_status=previous_bid_status,
                to_status=revision.status,
                metadata={"final_document_id": str(document.pk)},
            )
        return document


def fail_generation_job(
    *, job_id, safe_error_code, safe_error_message,
    diagnostic_reference, correlation_id
):
    with transaction.atomic():
        try:
            job = (
                DocumentGenerationJob.objects.select_for_update()
                .select_related("requested_by")
                .get(pk=job_id)
            )
        except DocumentGenerationJob.DoesNotExist:
            return None
        if job.status in {
            GenerationJobStatus.COMPLETED,
            GenerationJobStatus.FAILED,
        }:
            return job
        previous_status = job.status
        job.status = GenerationJobStatus.FAILED
        job.safe_error_code = safe_error_code
        job.safe_error_message = safe_error_message
        job.diagnostic_reference = diagnostic_reference
        job.completed_at = timezone.now()
        job.version += 1
        job.full_clean(validate_unique=False)
        job.save(
            update_fields=[
                "status", "safe_error_code", "safe_error_message",
                "diagnostic_reference", "completed_at", "version"
            ]
        )
        event = _write_job_event(
            job=job,
            action=DocumentAuditAction.FAILED,
            correlation_id=correlation_id,
            from_status=previous_status,
            to_status=job.status,
        )
        create_notification(
            recipient=job.requested_by,
            notification_type=NotificationType.DOCUMENT_FAILED,
            source_event_id=event.pk,
            source_entity_type="DocumentGenerationJob",
            source_entity_id=job.pk,
            title="Pembuatan dokumen gagal",
            message=(
                "Dokumen final belum dapat dibuat. Bid tetap "
                "ditandatangani dan dapat dicoba kembali."
            ),
        )
        return job


def get_authorized_document(*, actor, document_id):
    from apps.accounts.choices import UserRole
    from apps.accounts.policies import require_valid_role

    require_valid_role(actor)
    if actor.role not in {
        UserRole.PROCUREMENT_STAFF,
        UserRole.MANAGER,
    }:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("Anda tidak dapat mengunduh dokumen ini.")
    try:
        document = FinalDocument.objects.select_related(
            "bid_revision__bid_proposal"
        ).get(pk=document_id)
    except FinalDocument.DoesNotExist as error:
        raise ValidationError("Dokumen final tidak ditemukan.") from error
    if document.bid_revision.status != BidStatus.FINALIZED:
        raise InvalidTransition("Bid belum memiliki dokumen final valid.")
    try:
        content = read_private_object(document.object_key)
    except PrivateStorageError as error:
        logger.exception(
            "Final document storage unavailable",
            extra={
                "actor_id": str(actor.pk),
                "final_document_id": str(document.pk),
            },
        )
        raise InvalidTransition(
            "Dokumen sementara tidak dapat diakses. Silakan coba lagi."
        ) from error
    if (
        len(content) != document.size_bytes
        or hashlib.sha256(content).hexdigest() != document.sha256
        or not content.startswith(b"%PDF-")
    ):
        raise InvalidTransition("Integritas dokumen final tidak valid.")
    logger.info(
        "Final document downloaded",
        extra={
            "actor_id": str(actor.pk),
            "final_document_id": str(document.pk),
            "bid_revision_id": str(document.bid_revision_id),
        },
    )
    return document, content
