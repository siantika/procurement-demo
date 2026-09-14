import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.catalog.models import Product, Supplier
from apps.sourcing.models import ProcurementResult, SupplierOffer
from apps.tender.models import TenderRequest

from .choices import UserRole
from .test_seed_demo import PASSWORD_ENV

User = get_user_model()


class ResetDemoDataTests(TestCase):
    def seed(self):
        with patch.dict(os.environ, PASSWORD_ENV, clear=True):
            call_command("seed_demo", stdout=StringIO())

    def test_refuses_non_demo_environment(self):
        with self.assertRaises(CommandError):
            call_command(
                "reset_demo_data",
                confirm="DEMO_ONLY",
                stdout=StringIO(),
            )

    @override_settings(APP_ENV="demo")
    def test_requires_exact_confirmation(self):
        with self.assertRaises(CommandError):
            call_command(
                "reset_demo_data",
                confirm="wrong",
                stdout=StringIO(),
            )

    @override_settings(APP_ENV="demo")
    def test_reset_removes_only_canonical_seed_and_is_repeatable(self):
        self.seed()
        unrelated = User.objects.create_user(
            username="unrelated",
            email="unrelated@example.test",
            password="StrongPassword123!",
            full_name="Unrelated User",
            role=UserRole.PROCUREMENT_STAFF,
        )

        call_command(
            "reset_demo_data",
            confirm="DEMO_ONLY",
            stdout=StringIO(),
        )
        call_command(
            "reset_demo_data",
            confirm="DEMO_ONLY",
            stdout=StringIO(),
        )

        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(User.objects.filter(pk=unrelated.pk).exists())
        self.assertFalse(Product.objects.exists())
        self.assertFalse(Supplier.objects.exists())
        self.assertFalse(SupplierOffer.objects.exists())
        self.assertFalse(TenderRequest.objects.exists())
        self.assertFalse(ProcurementResult.objects.exists())
