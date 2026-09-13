import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.choices import UserRole
from apps.audit.models import AuditEvent
from apps.catalog.models import Product, Supplier

from .models import SupplierOffer
from .policies import (
    OfferEligibilityInput,
    calculate_net_purchase_price,
    evaluate_offer_eligibility,
)
from .selectors import evaluate_current_offer
from .services import (
    correct_unused_offer,
    create_supplier_offer,
    deactivate_supplier_offer,
    supersede_supplier_offer,
)

User = get_user_model()


class SupplierOfferFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="offer-admin",
            email="offer-admin@example.test",
            password="StrongPassword123!",
            full_name="Offer Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="offer-staff",
            email="offer-staff@example.test",
            password="StrongPassword123!",
            full_name="Offer Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.product = Product.objects.create(
            code="PUMP-001",
            name="Infusion Pump",
            default_unit="unit",
            created_by=cls.admin,
        )
        cls.supplier = Supplier.objects.create(
            code="SUP-A",
            name="Supplier A",
            created_by=cls.admin,
        )

    def correlation_id(self):
        return str(uuid.uuid4())

    def values(self, **overrides):
        values = {
            "supplier_id": self.supplier.pk,
            "product_id": self.product.pk,
            "supplier_reference": "OFF-A-001",
            "base_unit_price": Decimal("7000000.0000"),
            "discount_percent": Decimal("10.0000"),
            "available_quantity": Decimal("60.000"),
            "valid_from": date.today(),
            "valid_until": date.today() + timedelta(days=30),
        }
        values.update(overrides)
        return values

    def create_offer(self, **overrides):
        return create_supplier_offer(
            actor=self.staff,
            correlation_id=self.correlation_id(),
            **self.values(**overrides),
        )


class SupplierOfferTests(SupplierOfferFixtureMixin, TestCase):

    def test_golden_net_price(self):
        self.assertEqual(
            calculate_net_purchase_price("7000000", "10"),
            Decimal("6300000.0000"),
        )

    def test_staff_creates_offer_with_canonical_value_and_audit(self):
        offer = self.create_offer()
        self.assertEqual(offer.net_purchase_price, Decimal("6300000.0000"))
        self.assertEqual(offer.calculation_version, "calc-v1")
        self.assertTrue(
            AuditEvent.objects.filter(action="OFFER_CREATED").exists()
        )

    def test_admin_cannot_create_offer(self):
        with self.assertRaises(PermissionDenied):
            create_supplier_offer(
                actor=self.admin,
                correlation_id=self.correlation_id(),
                **self.values(),
            )

    def test_inactive_master_is_rejected(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            self.create_offer()

    def test_eligibility_checks_date_and_master_state(self):
        offer = self.create_offer()
        self.assertTrue(
            evaluate_current_offer(
                offer, as_of_date=offer.valid_from
            ).eligible
        )
        self.assertTrue(
            evaluate_current_offer(
                offer, as_of_date=offer.valid_until
            ).eligible
        )
        result = evaluate_current_offer(
            offer,
            as_of_date=offer.valid_until + timedelta(days=1),
        )
        self.assertFalse(result.eligible)
        self.assertEqual(result.code, "EXPIRED")

    def test_pure_eligibility_marks_zero_net_price_ineligible(self):
        result = evaluate_offer_eligibility(
            OfferEligibilityInput(
                offer_active=True,
                product_active=True,
                supplier_active=True,
                product_id=str(self.product.pk),
                currency="IDR",
                net_purchase_price=Decimal("0.0000"),
                available_quantity=None,
                valid_from=None,
                valid_until=None,
            ),
            as_of_date=date.today(),
        )

        self.assertFalse(result.eligible)
        self.assertEqual(result.code, "NON_POSITIVE_NET_PRICE")

    def test_discount_one_hundred_is_recorded_but_not_eligible(self):
        offer = self.create_offer(discount_percent=Decimal("100.0000"))

        self.assertEqual(offer.net_purchase_price, Decimal("0.0000"))
        self.assertFalse(
            evaluate_current_offer(offer, as_of_date=date.today()).eligible
        )

    def test_optional_supplier_reference_is_canonical_empty_string(self):
        offer = self.create_offer(supplier_reference=None)

        self.assertEqual(offer.supplier_reference, "")

    def test_correction_recalculates_price_and_uses_version(self):
        offer = self.create_offer()
        corrected = correct_unused_offer(
            actor=self.staff,
            offer_id=offer.pk,
            expected_version=offer.version,
            correlation_id=self.correlation_id(),
            **self.values(discount_percent=Decimal("5.0000")),
        )
        self.assertEqual(
            corrected.net_purchase_price, Decimal("6650000.0000")
        )
        self.assertEqual(corrected.version, 2)
        with self.assertRaises(ValidationError):
            correct_unused_offer(
                actor=self.staff,
                offer_id=offer.pk,
                expected_version=1,
                correlation_id=self.correlation_id(),
                **self.values(),
            )

    def test_supersede_preserves_old_offer(self):
        old_offer = self.create_offer()
        new_offer = supersede_supplier_offer(
            actor=self.staff,
            offer_id=old_offer.pk,
            expected_version=old_offer.version,
            correlation_id=self.correlation_id(),
            **self.values(base_unit_price=Decimal("6800000.0000")),
        )
        old_offer.refresh_from_db()
        self.assertFalse(old_offer.is_active)
        self.assertEqual(new_offer.supersedes_offer, old_offer)
        self.assertEqual(SupplierOffer.objects.count(), 2)
        old_event = AuditEvent.objects.get(
            entity_id=old_offer.pk,
            action="OFFER_SUPERSEDED",
        )
        new_event = AuditEvent.objects.get(
            entity_id=new_offer.pk,
            action="OFFER_CREATED",
        )
        self.assertEqual(
            old_event.metadata["replacement_offer_id"], str(new_offer.pk)
        )
        self.assertEqual(
            new_event.metadata["supersedes_offer_id"], str(old_offer.pk)
        )

    def test_correction_and_supersede_reject_identity_change(self):
        offer = self.create_offer()
        other_product = Product.objects.create(
            code="PUMP-002",
            name="Other Pump",
            default_unit="unit",
            created_by=self.admin,
        )
        for operation in (correct_unused_offer, supersede_supplier_offer):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(ValidationError):
                    operation(
                        actor=self.staff,
                        offer_id=offer.pk,
                        expected_version=offer.version,
                        correlation_id=self.correlation_id(),
                        **self.values(product_id=other_product.pk),
                    )

    def test_correcting_superseded_offer_is_rejected(self):
        old_offer = self.create_offer()
        supersede_supplier_offer(
            actor=self.staff,
            offer_id=old_offer.pk,
            expected_version=old_offer.version,
            correlation_id=self.correlation_id(),
            **self.values(),
        )
        old_offer.refresh_from_db()

        with self.assertRaisesMessage(
            ValidationError, "sudah memiliki histori"
        ):
            correct_unused_offer(
                actor=self.staff,
                offer_id=old_offer.pk,
                expected_version=old_offer.version,
                correlation_id=self.correlation_id(),
                **self.values(),
            )


class SupplierOfferViewTests(SupplierOfferFixtureMixin, TestCase):
    def test_only_staff_can_open_offer_list(self):
        url = reverse("sourcing:offer-list")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_open_offer_detail(self):
        offer = self.create_offer()
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("sourcing:offer-detail", args=[offer.pk])
        )
        self.assertContains(response, "Supplier A")

    def test_offer_list_explains_ineligible_offer(self):
        self.create_offer(discount_percent=Decimal("100.0000"))
        self.client.force_login(self.staff)

        response = self.client.get(reverse("sourcing:offer-list"))

        self.assertContains(response, "Tidak eligible")
        self.assertContains(response, "Harga net harus lebih dari nol.")

    def test_deactivate_rejects_missing_and_stale_version(self):
        offer = self.create_offer()
        self.client.force_login(self.staff)
        url = reverse("sourcing:offer-deactivate", args=[offer.pk])

        self.assertEqual(self.client.post(url).status_code, 400)
        deactivate_supplier_offer(
            actor=self.staff,
            offer_id=offer.pk,
            expected_version=offer.version,
            correlation_id=self.correlation_id(),
        )
        response = self.client.post(url, {"expected_version": 1})

        self.assertEqual(response.status_code, 409)
