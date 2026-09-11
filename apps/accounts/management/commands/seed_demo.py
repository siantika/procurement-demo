"""Seed akun demo canonical secara idempotent."""

import os
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.choices import AccountAuditAction, UserRole
from apps.audit.writer import write_audit_event

User = get_user_model()

DEMO_USERS = (
    {
        "username": "demo-admin",
        "email": "admin@example.test",
        "full_name": "Demo Admin",
        "role": UserRole.ADMIN,
        "password_env": "DEMO_ADMIN_PASSWORD",
    },
    {
        "username": "demo-staff",
        "email": "staff@example.test",
        "full_name": "Demo Procurement Staff",
        "role": UserRole.PROCUREMENT_STAFF,
        "password_env": "DEMO_STAFF_PASSWORD",
    },
    {
        "username": "demo-manager",
        "email": "manager@example.test",
        "full_name": "Demo Manager",
        "role": UserRole.MANAGER,
        "password_env": "DEMO_MANAGER_PASSWORD",
    },
)


class Command(BaseCommand):
    help = "Create or verify the three canonical demo accounts."

    def handle(self, *args, **options):
        passwords = self._load_passwords()
        correlation_id = str(uuid.uuid4())

        with transaction.atomic():
            for definition in DEMO_USERS:
                self._seed_user(
                    definition=definition,
                    password=passwords[definition["password_env"]],
                    correlation_id=correlation_id,
                )

        self.stdout.write(
            self.style.SUCCESS("Akun demo berhasil dibuat/diverifikasi.")
        )

    @staticmethod
    def _load_passwords():
        names = [item["password_env"] for item in DEMO_USERS]
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            joined_names = ", ".join(missing)
            raise CommandError(
                f"Environment password wajib diisi: {joined_names}"
            )
        return {name: os.environ[name] for name in names}

    def _seed_user(self, *, definition, password, correlation_id):
        user = User.objects.filter(
            username__iexact=definition["username"]
        ).first()
        created = user is None

        if created:
            candidate = User(
                username=definition["username"],
                email=definition["email"],
                full_name=definition["full_name"],
                role=definition["role"],
            )
            validate_password(password, user=candidate)
            user = User.objects.create_user(
                username=definition["username"],
                email=definition["email"],
                password=password,
                full_name=definition["full_name"],
                role=definition["role"],
            )
            changed_fields = []
        else:
            changed_fields = self._update_user(
                user=user,
                definition=definition,
                password=password,
            )

        if not created and not changed_fields:
            return

        write_audit_event(
            actor=None,
            entity_type="User",
            entity_id=user.pk,
            action=(
                AccountAuditAction.USER_CREATED
                if created
                else AccountAuditAction.USER_UPDATED
            ),
            correlation_id=correlation_id,
            to_status=user.role if created else None,
            metadata={
                "source": "seed_demo",
                "changed_fields": changed_fields,
            },
        )

    @staticmethod
    def _update_user(*, user, definition, password):
        changed_fields = []
        for field_name in ("email", "full_name", "role"):
            expected_value = definition[field_name]
            if getattr(user, field_name) != expected_value:
                setattr(user, field_name, expected_value)
                changed_fields.append(field_name)

        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")
        if not user.check_password(password):
            validate_password(password, user=user)
            user.set_password(password)
            changed_fields.append("password")

        if changed_fields:
            user.full_clean()
            user.save()
        return changed_fields
