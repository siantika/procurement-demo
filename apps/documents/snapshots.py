from datetime import timedelta

from apps.sourcing.snapshots import timestamp_string


def build_finalization_snapshot(
    *, revision, approval, signature, document_number,
    document_version, template_version, captured_at
):
    result_snapshot = revision.selected_result_snapshot
    return {
        "schema_version": 1,
        "snapshot_type": "bid_finalization",
        "captured_at": timestamp_string(captured_at),
        "source": {
            "bid_proposal_id": str(revision.bid_proposal_id),
            "proposal_number": revision.bid_proposal.proposal_number,
            "bid_revision_id": str(revision.pk),
            "bid_revision_number": revision.revision_number,
            "submission_hash": revision.submission_hash,
            "approval_decision_id": str(approval.pk),
            "signature_id": str(signature.pk),
        },
        "document": {
            "document_number": document_number,
            "document_version": document_version,
            "template_version": template_version,
            "valid_until": (
                captured_at.date() + timedelta(days=30)
            ).isoformat(),
        },
        "tender": result_snapshot["tender"],
        "pricing": revision.submission_snapshot["data"],
        "approval": {
            "decision": approval.decision,
            "manager_name": (
                approval.decided_by.full_name
                or approval.decided_by.username
            ),
            "decided_at": timestamp_string(approval.decided_at),
            "submission_hash": approval.submission_hash,
        },
        "signature": {
            "signer_name": signature.signer_name,
            "signed_at": timestamp_string(signature.signed_at),
            "signed_snapshot_hash": signature.signed_snapshot_hash,
            "has_image": bool(signature.image_object_key),
            "image_object_key": signature.image_object_key,
            "image_version_id": signature.image_version_id,
            "image_mime_type": signature.image_mime_type,
            "image_size_bytes": signature.image_size_bytes,
            "image_sha256": signature.image_sha256,
        },
    }
