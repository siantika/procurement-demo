"""Model pengguna untuk aplikasi accounts."""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from .choices import UserRole


class User(AbstractUser):
    """Custom user dengan UUID dan peran bisnis."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_user"
