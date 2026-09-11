"""Model pengguna untuk aplikasi accounts."""

import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower

from .choices import UserRole


class AccountUserManager(UserManager):
    """Buat user dengan identity dan role bisnis yang valid."""

    def create_user(
        self,
        username,
        email=None,
        password=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError("User harus memiliki email.")
        if not extra_fields.get("full_name"):
            raise ValueError("User harus memiliki full_name.")
        if extra_fields.get("role") not in UserRole.values:
            raise ValueError("User harus memiliki role yang valid.")

        extra_fields["is_staff"] = extra_fields["role"] == UserRole.ADMIN
        return super().create_user(
            username,
            email,
            password,
            **extra_fields,
        )

    def create_superuser(
        self,
        username,
        email=None,
        password=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError("Superuser harus memiliki email.")
        extra_fields.setdefault("role", UserRole.ADMIN)
        if not extra_fields.get("full_name"):
            raise ValueError("Superuser harus memiliki full_name.")
        if extra_fields["role"] != UserRole.ADMIN:
            raise ValueError("Superuser harus memiliki role ADMIN.")

        return super().create_superuser(
            username,
            email,
            password,
            **extra_fields,
        )


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

    objects = AccountUserManager()

    REQUIRED_FIELDS = ["email", "full_name", "role"]

    class Meta:
        db_table = "accounts_user"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=UserRole.values),
                name="accounts_user_role_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_staff=False)
                    | models.Q(role=UserRole.ADMIN)
                ),
                name="accounts_user_staff_requires_admin_role",
            ),
            models.UniqueConstraint(
                Lower("username"),
                name="accounts_user_username_ci_unique",
            ),
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
            ),
        ]

    def clean(self):
        """Normalisasi email dan validasi field model."""

        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)
        self.is_staff = self.role == UserRole.ADMIN

    def save(self, *args, **kwargs):
        """Jaga agar akses Django Admin selalu mengikuti role bisnis."""

        self.is_staff = self.role == UserRole.ADMIN
        if update_fields := kwargs.get("update_fields"):
            kwargs["update_fields"] = set(update_fields) | {"is_staff"}
        return super().save(*args, **kwargs)
