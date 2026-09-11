"""Pilihan nilai yang digunakan model accounts."""

from django.db import models


class UserRole(models.TextChoices):
    """Peran bisnis yang tersedia untuk pengguna."""

    ADMIN = "ADMIN", "Admin"
    PROCUREMENT_STAFF = "PROCUREMENT_STAFF", "Procurement Staff"
    MANAGER = "MANAGER", "Manager"
