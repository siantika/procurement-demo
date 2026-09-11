"""Tests untuk model dan writer audit."""

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.accounts.choices import UserRole

from .models import AuditEvent
from .writer import write_audit_event

User = get_user_model()


class AuditEventTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_user(
            username="audit-admin",
            email="audit-admin@example.com",
            password="StrongPassword123!",
            full_name="Audit Admin",
            role=UserRole.ADMIN,
        )

    def create_event(self, **overrides):
        data = {
            "actor": self.actor,
            "entity_type": "User",
            "entity_id": uuid.uuid4(),
            "action": "USER_CREATED",
            "correlation_id": str(uuid.uuid4()),
        }
        data.update(overrides)
        return write_audit_event(**data)

    def test_writer_freezes_actor_name(self):
        event = self.create_event()
        self.actor.full_name = "Changed Name"
        self.actor.save(update_fields=["full_name"])

        event.refresh_from_db()
        self.assertEqual(event.actor_name, "Audit Admin")

    def test_writer_supports_system_actor(self):
        event = self.create_event(actor=None)

        self.assertIsNone(event.actor)
        self.assertEqual(event.actor_name, "System")

    def test_writer_rejects_invalid_correlation_id(self):
        for correlation_id in ("", "x" * 101):
            with self.subTest(correlation_id=correlation_id):
                with self.assertRaises(ValueError):
                    self.create_event(correlation_id=correlation_id)

    def test_event_cannot_be_updated(self):
        event = self.create_event()
        event.action = "CHANGED"

        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).update(action="CHANGED")

    def test_event_cannot_be_deleted(self):
        event = self.create_event()

        with self.assertRaises(ValidationError):
            event.delete()
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).delete()

    def test_actor_is_protected_from_deletion(self):
        self.create_event()

        with self.assertRaises(ProtectedError):
            self.actor.delete()

    def test_database_rejects_non_positive_revision(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_event(entity_revision=0)
