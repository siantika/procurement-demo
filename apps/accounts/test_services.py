"""Integration tests untuk account application services."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.audit.models import AuditEvent

from .choices import AccountAuditAction, UserRole
from .services import change_user_role, create_user, deactivate_user

User = get_user_model()


class AccountServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="service-admin",
            email="service-admin@example.com",
            password="StrongPassword123!",
            full_name="Service Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="service-staff",
            email="service-staff@example.com",
            password="StrongPassword123!",
            full_name="Service Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.target = User.objects.create_user(
            username="service-target",
            email="service-target@example.com",
            password="StrongPassword123!",
            full_name="Service Target",
            role=UserRole.MANAGER,
        )

    def correlation_id(self):
        return str(uuid.uuid4())

    def test_admin_can_create_user_with_audit(self):
        correlation_id = self.correlation_id()

        user = create_user(
            actor=self.admin,
            username="created-by-service",
            email="created-by-service@example.com",
            password="StrongPassword123!",
            full_name="Created By Service",
            role=UserRole.ADMIN,
            correlation_id=correlation_id,
        )

        self.assertTrue(user.check_password("StrongPassword123!"))
        self.assertTrue(user.is_staff)
        event = AuditEvent.objects.get(entity_id=user.pk)
        self.assertEqual(event.action, AccountAuditAction.USER_CREATED)
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.correlation_id, correlation_id)

    def test_non_admin_cannot_create_user(self):
        with self.assertRaises(PermissionDenied):
            create_user(
                actor=self.staff,
                username="forbidden-user",
                email="forbidden-user@example.com",
                password="StrongPassword123!",
                full_name="Forbidden User",
                role=UserRole.MANAGER,
                correlation_id=self.correlation_id(),
            )

        self.assertFalse(
            User.objects.filter(username="forbidden-user").exists()
        )
        self.assertFalse(AuditEvent.objects.exists())

    def test_create_user_rejects_weak_password(self):
        with self.assertRaises(ValidationError):
            create_user(
                actor=self.admin,
                username="weak-password-user",
                email="weak-password-user@example.com",
                password="password",
                full_name="Weak Password User",
                role=UserRole.MANAGER,
                correlation_id=self.correlation_id(),
            )

        self.assertFalse(
            User.objects.filter(username="weak-password-user").exists()
        )
        self.assertFalse(AuditEvent.objects.exists())

    def test_create_user_rejects_case_insensitive_duplicate_identity(self):
        duplicate_values = (
            {
                "username": self.target.username.upper(),
                "email": "unique-service@example.com",
            },
            {
                "username": "unique-service-user",
                "email": self.target.email.upper(),
            },
        )

        for identity in duplicate_values:
            with self.subTest(identity=identity):
                with self.assertRaises(ValidationError):
                    create_user(
                        actor=self.admin,
                        password="StrongPassword123!",
                        full_name="Duplicate Identity",
                        role=UserRole.MANAGER,
                        correlation_id=self.correlation_id(),
                        **identity,
                    )

        self.assertFalse(AuditEvent.objects.exists())

    def test_change_role_locks_updates_and_audits(self):
        previous_role = self.target.role

        user = change_user_role(
            actor=self.admin,
            user_id=self.target.pk,
            role=UserRole.ADMIN,
            correlation_id=self.correlation_id(),
        )

        self.assertTrue(user.is_staff)
        event = AuditEvent.objects.get(entity_id=user.pk)
        self.assertEqual(
            event.action,
            AccountAuditAction.USER_ROLE_CHANGED,
        )
        self.assertEqual(event.from_status, previous_role)
        self.assertEqual(event.to_status, UserRole.ADMIN)

    def test_unchanged_role_does_not_create_audit(self):
        change_user_role(
            actor=self.admin,
            user_id=self.target.pk,
            role=self.target.role,
            correlation_id=self.correlation_id(),
        )

        self.assertFalse(AuditEvent.objects.exists())

    def test_deactivate_user_preserves_row_and_creates_audit(self):
        user = deactivate_user(
            actor=self.admin,
            user_id=self.target.pk,
            correlation_id=self.correlation_id(),
        )

        self.assertFalse(user.is_active)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        event = AuditEvent.objects.get(entity_id=user.pk)
        self.assertEqual(
            event.action,
            AccountAuditAction.USER_DEACTIVATED,
        )

    def test_audit_failure_rolls_back_user_creation(self):
        with (
            patch(
                "apps.accounts.services.write_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            create_user(
                actor=self.admin,
                username="rolled-back-user",
                email="rolled-back-user@example.com",
                password="StrongPassword123!",
                full_name="Rolled Back User",
                role=UserRole.MANAGER,
                correlation_id=self.correlation_id(),
            )

        self.assertFalse(
            User.objects.filter(username="rolled-back-user").exists()
        )
