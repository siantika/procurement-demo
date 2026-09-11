"""Writer tunggal untuk membuat event audit yang aman."""

from .models import AuditEvent


def write_audit_event(
    *,
    actor,
    entity_type,
    entity_id,
    action,
    correlation_id,
    entity_revision=None,
    from_status=None,
    to_status=None,
    reason=None,
    metadata=None,
):
    """Simpan satu event tanpa payload atau credential sensitif."""

    normalized_correlation_id = str(correlation_id).strip()
    if not normalized_correlation_id:
        raise ValueError("correlation_id wajib diisi.")
    if len(normalized_correlation_id) > 100:
        raise ValueError("correlation_id maksimal 100 karakter.")

    actor_name = "System"
    if actor is not None:
        actor_name = actor.full_name or actor.username

    return AuditEvent.objects.create(
        actor=actor,
        actor_name=actor_name,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_revision=entity_revision,
        action=action,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        metadata=metadata or {},
        correlation_id=normalized_correlation_id,
    )
