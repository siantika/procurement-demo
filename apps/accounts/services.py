"""Transactional application services untuk mutation account."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.writer import write_audit_event

from .choices import AccountAuditAction, UserRole
from .policies import require_admin

User = get_user_model()


def _write_user_event(
    *,
    actor,
    user,
    action,
    correlation_id,
    from_status=None,
    to_status=None,
    metadata=None,
):
    return write_audit_event(
        actor=actor,
        entity_type="User",
        entity_id=user.pk,
        action=action,
        correlation_id=correlation_id,
        from_status=from_status,
        to_status=to_status,
        metadata=metadata,
    )


def create_user(
    *,
    actor,
    username,
    email,
    password,
    full_name,
    role,
    correlation_id,
):
    """Buat user dan audit event dalam satu transaction."""

    require_admin(actor)
    with transaction.atomic():
        candidate = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role,
        )
        candidate.full_clean(exclude=("password",))
        validate_password(password, user=candidate)
        user = User.objects.create_user(
            username=candidate.username,
            email=candidate.email,
            password=password,
            full_name=candidate.full_name,
            role=candidate.role,
        )
        _write_user_event(
            actor=actor,
            user=user,
            action=AccountAuditAction.USER_CREATED,
            correlation_id=correlation_id,
            to_status=user.role,
        )
        return user


def change_user_role(*, actor, user_id, role, correlation_id):
    """Ubah role user menggunakan row lock dan catat audit."""

    require_admin(actor)
    if role not in UserRole.values:
        raise ValidationError({"role": "Role user tidak valid."})

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)
        previous_role = user.role
        if previous_role == role:
            return user

        user.role = role
        user.full_clean()
        user.save(update_fields=["role", "updated_at"])
        _write_user_event(
            actor=actor,
            user=user,
            action=AccountAuditAction.USER_ROLE_CHANGED,
            correlation_id=correlation_id,
            from_status=previous_role,
            to_status=user.role,
        )
        return user


def deactivate_user(*, actor, user_id, correlation_id):
    """Nonaktifkan user tanpa hard-delete dan catat audit."""

    require_admin(actor)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)
        if not user.is_active:
            return user

        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        _write_user_event(
            actor=actor,
            user=user,
            action=AccountAuditAction.USER_DEACTIVATED,
            correlation_id=correlation_id,
            from_status="ACTIVE",
            to_status="INACTIVE",
        )
        return user


def save_user_from_admin(*, actor, user, correlation_id):
    """Simpan form Django Admin melalui service dan audit mutation."""

    require_admin(actor)
    with transaction.atomic():
        is_new = user._state.adding
        previous = None
        if not is_new:
            previous = User.objects.select_for_update().get(pk=user.pk)

        user.full_clean()
        user.save()

        if is_new:
            _write_user_event(
                actor=actor,
                user=user,
                action=AccountAuditAction.USER_CREATED,
                correlation_id=correlation_id,
                to_status=user.role,
            )
            return user

        changed_fields = []
        for field_name in ("username", "email", "full_name"):
            if getattr(previous, field_name) != getattr(user, field_name):
                changed_fields.append(field_name)

        if changed_fields:
            _write_user_event(
                actor=actor,
                user=user,
                action=AccountAuditAction.USER_UPDATED,
                correlation_id=correlation_id,
                metadata={"changed_fields": changed_fields},
            )
        if previous.role != user.role:
            _write_user_event(
                actor=actor,
                user=user,
                action=AccountAuditAction.USER_ROLE_CHANGED,
                correlation_id=correlation_id,
                from_status=previous.role,
                to_status=user.role,
            )
        if previous.is_active and not user.is_active:
            _write_user_event(
                actor=actor,
                user=user,
                action=AccountAuditAction.USER_DEACTIVATED,
                correlation_id=correlation_id,
                from_status="ACTIVE",
                to_status="INACTIVE",
            )
        return user
