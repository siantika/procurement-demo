"""Controlled signing service for approved Bid revisions."""

import hashlib
import logging
import uuid
from io import BytesIO

from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.db import IntegrityError, transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.accounts.policies import require_manager
from apps.approval.choices import ApprovalDecisionType
from apps.audit.writer import write_audit_event
from apps.bids.choices import BidStatus
from apps.bids.models import BidProposalRevision
from apps.core.domain.canonical_json import canonical_hash
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.documents.storage import (
    PrivateStorageError,
    store_private_object,
)

from .choices import SignatureAuditAction
from .models import Signature

logger = logging.getLogger(__name__)


def _validate_image(upload):
    if upload is None:
        return None
    content = upload.read()
    if not content or len(content) > 1_048_576:
        raise ValidationError(
            "Ukuran gambar tanda tangan harus 1 byte sampai 1 MiB."
        )
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            image_format = image.format
    except (UnidentifiedImageError, OSError) as error:
        raise ValidationError(
            "File tanda tangan bukan gambar yang valid."
        ) from error
    mime_type = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(
        image_format
    )
    if mime_type is None:
        raise ValidationError(
            "Gambar tanda tangan harus berupa PNG atau JPEG."
        )
    if not (200 <= width <= 2000 and 80 <= height <= 1000):
        raise ValidationError(
            "Resolusi gambar harus 200×80 sampai 2000×1000 piksel."
        )
    return {
        "content": content,
        "mime_type": mime_type,
        "sha256": hashlib.sha256(content).hexdigest(),
        "extension": "png" if image_format == "PNG" else "jpg",
    }


def _assert_approved_revision(*, revision, expected_version, actor):
    if revision.status != BidStatus.APPROVED:
        raise InvalidTransition(
            "Hanya Bid APPROVED yang dapat ditandatangani."
        )
    if revision.version != expected_version:
        raise ConcurrencyConflict("Bid telah berubah. Muat ulang halaman.")
    try:
        approval = revision.approval_decision
    except ObjectDoesNotExist as error:
        raise InvalidTransition("Approval Bid tidak ditemukan.") from error
    if (
        approval.decision != ApprovalDecisionType.APPROVED
        or approval.decided_by_id != actor.pk
    ):
        raise PermissionDenied(
            "Hanya Manager yang menyetujui Bid ini yang dapat sign."
        )
    if (
        not revision.submission_hash
        or approval.submission_hash != revision.submission_hash
        or canonical_hash(revision.submission_snapshot)
        != revision.submission_hash
    ):
        raise InvalidTransition(
            "Hash submission atau approval tidak valid."
        )
    if Signature.objects.filter(bid_revision=revision).exists():
        raise ConcurrencyConflict("Bid ini sudah ditandatangani.")
    return revision, approval


def _approved_revision_queryset():
    return BidProposalRevision.objects.select_related(
        "bid_proposal", "approval_decision__decided_by"
    )


def _locked_approved_revision(*, revision_id, expected_version, actor):
    try:
        revision = _approved_revision_queryset().select_for_update(
            of=("self",)
        ).get(pk=revision_id)
    except BidProposalRevision.DoesNotExist as error:
        raise ValidationError("Bid revision tidak ditemukan.") from error
    return _assert_approved_revision(
        revision=revision,
        expected_version=expected_version,
        actor=actor,
    )


def sign_bid(
    *, actor, revision_id, expected_version, correlation_id,
    signature_image=None
):
    require_manager(actor)
    try:
        preflight = _approved_revision_queryset().get(pk=revision_id)
    except BidProposalRevision.DoesNotExist as error:
        raise ValidationError("Bid revision tidak ditemukan.") from error
    _assert_approved_revision(
        revision=preflight,
        expected_version=expected_version,
        actor=actor,
    )
    image = _validate_image(signature_image)
    image_metadata = {}
    if image is not None:
        object_key = (
            f"signatures/{revision_id}/{uuid.uuid4()}."
            f"{image['extension']}"
        )
        try:
            stored = store_private_object(
                object_key=object_key,
                content=image["content"],
                content_type=image["mime_type"],
            )
        except PrivateStorageError as error:
            logger.exception(
                "Signature image storage unavailable",
                extra={"bid_revision_id": str(revision_id)},
            )
            raise ValidationError(
                "Gambar signature belum dapat disimpan. Coba kembali."
            ) from error
        image_metadata = {
            "image_object_key": stored.object_key,
            "image_version_id": stored.version_id,
            "image_mime_type": image["mime_type"],
            "image_size_bytes": stored.size,
            "image_sha256": image["sha256"],
        }
    with transaction.atomic():
        revision, approval = _locked_approved_revision(
            revision_id=revision_id,
            expected_version=expected_version,
            actor=actor,
        )
        signature = Signature(
            bid_revision=revision,
            approval_decision=approval,
            signed_by=actor,
            signer_name=actor.full_name or actor.username,
            signed_snapshot_hash=revision.submission_hash,
            signed_at=timezone.now(),
            **image_metadata,
        )
        signature.full_clean()
        try:
            signature.save()
        except IntegrityError as error:
            raise ConcurrencyConflict(
                "Bid ini sudah ditandatangani."
            ) from error
        previous_status = revision.status
        revision.status = BidStatus.SIGNED
        revision.version += 1
        revision.full_clean()
        revision.save(update_fields=["status", "version", "updated_at"])
        write_audit_event(
            actor=actor,
            entity_type="BidProposalRevision",
            entity_id=revision.pk,
            entity_revision=revision.version,
            action=SignatureAuditAction.SIGNED,
            correlation_id=correlation_id,
            from_status=previous_status,
            to_status=revision.status,
            metadata={
                "bid_proposal_id": str(revision.bid_proposal_id),
                "proposal_number": revision.bid_proposal.proposal_number,
                "signature_id": str(signature.pk),
                "has_image": image is not None,
            },
        )
        return signature
