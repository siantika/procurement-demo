"""Authorization policy untuk modul accounts."""

from django.core.exceptions import PermissionDenied

from .choices import UserRole


def require_active_user(user):
    """Pastikan actor sudah login dan account-nya masih aktif."""

    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Account aktif diperlukan.")

    return user


def require_valid_role(user):
    """Pastikan actor aktif mempunyai role bisnis yang dikenal."""

    require_active_user(user)
    if user.role not in UserRole.values:
        raise PermissionDenied("Role account tidak valid.")

    return user


def require_role(user, expected_role):
    """Pastikan actor aktif mempunyai role bisnis yang diharapkan."""

    require_valid_role(user)
    if user.role != expected_role:
        raise PermissionDenied(
            "Anda tidak memiliki akses untuk tindakan ini."
        )

    return user


def require_admin(user):
    """Batasi tindakan untuk role Admin."""

    return require_role(user, UserRole.ADMIN)


def require_procurement_staff(user):
    """Batasi tindakan untuk role Procurement Staff."""

    return require_role(user, UserRole.PROCUREMENT_STAFF)


def require_manager(user):
    """Batasi tindakan untuk role Manager."""

    return require_role(user, UserRole.MANAGER)
