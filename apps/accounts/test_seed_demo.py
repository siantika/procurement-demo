"""Tests untuk command seed_demo."""

import os
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.audit.models import AuditEvent
from apps.catalog.models import Product, Supplier
from apps.sourcing.models import ProcurementResult, SupplierOffer
from apps.tender.models import TenderRequest
from apps.tender.services import get_current_tender_revision

from .choices import UserRole

User = get_user_model()

PASSWORD_ENV = {
    "DEMO_ADMIN_PASSWORD": "DemoAdminPassword123!",
    "DEMO_STAFF_PASSWORD": "DemoStaffPassword123!",
    "DEMO_MANAGER_PASSWORD": "DemoManagerPassword123!",
}


class SeedDemoCommandTests(TestCase):
    def test_requires_password_environment(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaises(CommandError),
        ):
            call_command("seed_demo", stdout=StringIO())

    def test_creates_three_users_without_printing_passwords(self):
        output = StringIO()

        with patch.dict(os.environ, PASSWORD_ENV, clear=True):
            call_command("seed_demo", stdout=output)

        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(AuditEvent.objects.count(), 13)
        expected_users = (
            ("demo-admin", UserRole.ADMIN, True),
            ("demo-staff", UserRole.PROCUREMENT_STAFF, False),
            ("demo-manager", UserRole.MANAGER, False),
        )
        for username, role, is_staff in expected_users:
            with self.subTest(username=username):
                user = User.objects.get(username=username)
                self.assertEqual(user.role, role)
                self.assertEqual(user.is_staff, is_staff)

        for password in PASSWORD_ENV.values():
            self.assertNotIn(password, output.getvalue())

        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Supplier.objects.count(), 3)
        self.assertEqual(SupplierOffer.objects.count(), 3)
        self.assertEqual(TenderRequest.objects.count(), 1)
        self.assertEqual(ProcurementResult.objects.count(), 1)
        result = ProcurementResult.objects.get()
        self.assertEqual(result.status, "VALID")
        self.assertEqual(result.total_purchase, Decimal("663000000.00"))
        tender = TenderRequest.objects.get(internal_code="DEMO-TENDER-001")
        revision = get_current_tender_revision(tender.pk)
        self.assertEqual(str(revision.total_hps), "800000000.00")
        self.assertEqual(
            str(revision.items.get().requested_quantity), "100.000"
        )
        prices = set(
            SupplierOffer.objects.values_list(
                "net_purchase_price", flat=True
            )
        )
        self.assertSetEqual(
            prices,
            {
                Decimal("6300000.0000"),
                Decimal("7125000.0000"),
                Decimal("7200000.0000"),
            },
        )
        self.assertFalse(
            SupplierOffer.objects.exclude(valid_until="2030-12-31").exists()
        )

    def test_repeated_seed_does_not_duplicate_data_or_audit(self):
        with patch.dict(os.environ, PASSWORD_ENV, clear=True):
            call_command("seed_demo", stdout=StringIO())
            call_command("seed_demo", stdout=StringIO())

        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Supplier.objects.count(), 3)
        self.assertEqual(SupplierOffer.objects.count(), 3)
        self.assertEqual(TenderRequest.objects.count(), 1)
        self.assertEqual(ProcurementResult.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 13)
