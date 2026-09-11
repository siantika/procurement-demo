"""Pilihan nilai yang digunakan model accounts."""

from django.db import models


class UserRole(models.TextChoices):
    """Peran bisnis yang tersedia untuk pengguna."""

    ADMIN = "ADMIN", "Admin"
    PROCUREMENT_STAFF = "PROCUREMENT_STAFF", "Procurement Staff"
    MANAGER = "MANAGER", "Manager"


class AccountAuditAction(models.TextChoices):
    """Action audit yang dimiliki modul accounts."""

    USER_CREATED = "USER_CREATED", "User created"
    USER_UPDATED = "USER_UPDATED", "User updated"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED", "User role changed"
    USER_DEACTIVATED = "USER_DEACTIVATED", "User deactivated"
