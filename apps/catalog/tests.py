import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.choices import UserRole
from apps.audit.models import AuditEvent

from .models import Product, Supplier
from .services import (
    create_product,
    create_supplier,
    deactivate_product,
    reactivate_product,
    update_product,
)

User = get_user_model()


class CatalogServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="catalog-admin",
            email="catalog-admin@example.test",
            password="StrongPassword123!",
            full_name="Catalog Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="catalog-staff",
            email="catalog-staff@example.test",
            password="StrongPassword123!",
            full_name="Catalog Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )

    def correlation_id(self):
        return str(uuid.uuid4())

    def test_admin_creates_product_and_supplier_with_audit(self):
        product = create_product(
            actor=self.admin,
            code="PUMP-001",
            name="Infusion Pump",
            description="Medical pump",
            default_unit="unit",
            correlation_id=self.correlation_id(),
        )
        supplier = create_supplier(
            actor=self.admin,
            code="SUP-A",
            name="Supplier A",
            contact_name="Ayu",
            email="ayu@example.test",
            phone="021-0001",
            address="Jakarta",
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(product.version, 1)
        self.assertEqual(supplier.version, 1)
        self.assertSetEqual(
            set(AuditEvent.objects.values_list("action", flat=True)),
            {"PRODUCT_CREATED", "SUPPLIER_CREATED"},
        )

    def test_staff_cannot_create_master_data(self):
        with self.assertRaises(PermissionDenied):
            create_product(
                actor=self.staff,
                code="FORBIDDEN",
                name="Forbidden",
                description="",
                default_unit="unit",
                correlation_id=self.correlation_id(),
            )
        self.assertFalse(Product.objects.exists())

    def test_product_code_is_case_insensitive_unique(self):
        self._product()
        with self.assertRaises(ValidationError):
            create_product(
                actor=self.admin,
                code="pump-001",
                name="Duplicate",
                description="",
                default_unit="unit",
                correlation_id=self.correlation_id(),
            )

    def test_product_code_is_cleaned_to_uppercase(self):
        product = create_product(
            actor=self.admin,
            code="PuMp-001 ",
            name="Infusion Pump",
            description="",
            default_unit="unit",
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(product.code, "PUMP-001")

    def test_supplier_code_is_cleaned_to_uppercase(self):
        supplier = create_supplier(
            actor=self.admin,
            code=" sup-a ",
            name="Supplier A",
            contact_name="",
            email="",
            phone="",
            address="",
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(supplier.code, "SUP-A")

    def test_equivalent_code_update_does_not_increment_version(self):
        product = self._product()

        updated = update_product(
            actor=self.admin,
            product_id=product.pk,
            expected_version=product.version,
            code=" pump-001 ",
            name=product.name,
            description=product.description,
            default_unit=product.default_unit,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(updated.code, "PUMP-001")
        self.assertEqual(updated.version, 1)
        self.assertFalse(
            AuditEvent.objects.filter(action="PRODUCT_UPDATED").exists()
        )

    def test_optional_text_is_canonical_empty_string(self):
        product = create_product(
            actor=self.admin,
            code="EMPTY-TEXT",
            name="Empty Text",
            description=None,
            default_unit="unit",
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(product.description, "")

    def test_database_enforces_case_insensitive_supplier_code(self):
        supplier = self._supplier()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Supplier.objects.create(
                code=supplier.code.lower(),
                name="Duplicate",
                created_by=self.admin,
            )

    def test_update_uses_version_and_audits_changed_fields(self):
        product = self._product()
        updated = update_product(
            actor=self.admin,
            product_id=product.pk,
            expected_version=1,
            name="Infusion Pump Pro",
            code=product.code,
            description=product.description,
            default_unit=product.default_unit,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(updated.version, 2)
        event = AuditEvent.objects.get(action="PRODUCT_UPDATED")
        self.assertEqual(event.metadata["changed_fields"], ["name"])
        with self.assertRaises(ValidationError):
            update_product(
                actor=self.admin,
                product_id=product.pk,
                expected_version=1,
                name="Stale change",
                code=product.code,
                description=product.description,
                default_unit=product.default_unit,
                correlation_id=self.correlation_id(),
            )

    def test_deactivate_preserves_product(self):
        product = self._product()
        result = deactivate_product(
            actor=self.admin,
            product_id=product.pk,
            expected_version=product.version,
            correlation_id=self.correlation_id(),
        )
        self.assertFalse(result.is_active)
        self.assertEqual(result.version, 2)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_admin_reactivates_product_with_audit(self):
        product = self._product()
        product = deactivate_product(
            actor=self.admin,
            product_id=product.pk,
            expected_version=product.version,
            correlation_id=self.correlation_id(),
        )

        reactivated = reactivate_product(
            actor=self.admin,
            product_id=product.pk,
            expected_version=product.version,
            correlation_id=self.correlation_id(),
        )

        self.assertTrue(reactivated.is_active)
        self.assertEqual(reactivated.version, 3)
        event = AuditEvent.objects.get(action="PRODUCT_REACTIVATED")
        self.assertEqual(event.actor, self.admin)

    def test_staff_cannot_reactivate_product(self):
        product = self._product()
        product.is_active = False
        product.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            reactivate_product(
                actor=self.staff,
                product_id=product.pk,
                expected_version=product.version,
                correlation_id=self.correlation_id(),
            )

    def _product(self):
        return create_product(
            actor=self.admin,
            code="PUMP-001",
            name="Infusion Pump",
            description="Medical pump",
            default_unit="unit",
            correlation_id=self.correlation_id(),
        )

    def _supplier(self):
        return create_supplier(
            actor=self.admin,
            code="SUP-A",
            name="Supplier A",
            contact_name="",
            email="",
            phone="",
            address="",
            correlation_id=self.correlation_id(),
        )


class CatalogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="view-admin",
            email="view-admin@example.test",
            password="StrongPassword123!",
            full_name="View Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="view-staff",
            email="view-staff@example.test",
            password="StrongPassword123!",
            full_name="View Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )

    def test_anonymous_redirected_and_staff_forbidden(self):
        url = reverse("catalog:product-list")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_can_create_product_through_ui(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("catalog:product-create"),
            {
                "code": "UI-001",
                "name": "UI Product",
                "description": "",
                "default_unit": "unit",
            },
        )
        self.assertRedirects(response, reverse("catalog:product-list"))
        self.assertTrue(Product.objects.filter(code="UI-001").exists())

    def test_admin_can_open_product_and_supplier_details(self):
        product = Product.objects.create(
            code="DETAIL-P",
            name="Detail Product",
            default_unit="unit",
            created_by=self.admin,
        )
        supplier = Supplier.objects.create(
            code="DETAIL-S",
            name="Detail Supplier",
            created_by=self.admin,
        )
        self.client.force_login(self.admin)

        product_response = self.client.get(
            reverse("catalog:product-detail", args=[product.pk])
        )
        supplier_response = self.client.get(
            reverse("catalog:supplier-detail", args=[supplier.pk])
        )

        self.assertContains(product_response, "Detail Product")
        self.assertContains(supplier_response, "Detail Supplier")

    def test_deactivate_rejects_missing_and_stale_version(self):
        product = Product.objects.create(
            code="STALE-P",
            name="Stale Product",
            default_unit="unit",
            created_by=self.admin,
        )
        self.client.force_login(self.admin)
        url = reverse("catalog:product-deactivate", args=[product.pk])

        self.assertEqual(self.client.post(url).status_code, 400)
        update_product(
            actor=self.admin,
            product_id=product.pk,
            expected_version=1,
            code=product.code,
            name="Changed Product",
            description=product.description,
            default_unit=product.default_unit,
            correlation_id=str(uuid.uuid4()),
        )
        response = self.client.post(url, {"expected_version": 1})

        self.assertEqual(response.status_code, 409)
        product.refresh_from_db()
        self.assertTrue(product.is_active)

    def test_admin_can_reactivate_product_through_ui(self):
        product = Product.objects.create(
            code="REACTIVE-P",
            name="Reactivate Product",
            default_unit="unit",
            is_active=False,
            created_by=self.admin,
        )
        self.client.force_login(self.admin)

        list_response = self.client.get(reverse("catalog:product-list"))
        response = self.client.post(
            reverse("catalog:product-reactivate", args=[product.pk]),
            {"expected_version": product.version},
        )

        self.assertContains(list_response, "Aktifkan kembali")
        self.assertRedirects(response, reverse("catalog:product-list"))
        product.refresh_from_db()
        self.assertTrue(product.is_active)
        self.assertEqual(product.version, 2)

        self.client.force_login(self.staff)
        tender_response = self.client.get(reverse("tender:create"))
        self.assertContains(tender_response, "Reactivate Product")

    def test_reactivate_rejects_missing_and_stale_version(self):
        product = Product.objects.create(
            code="REACTIVE-STALE",
            name="Reactivate Stale",
            default_unit="unit",
            is_active=False,
            created_by=self.admin,
        )
        self.client.force_login(self.admin)
        url = reverse("catalog:product-reactivate", args=[product.pk])

        self.assertEqual(self.client.post(url).status_code, 400)
        Product.objects.filter(pk=product.pk).update(version=2)
        response = self.client.post(url, {"expected_version": 1})

        self.assertEqual(response.status_code, 409)
        product.refresh_from_db()
        self.assertFalse(product.is_active)

    def test_update_returns_conflict_for_stale_form(self):
        product = Product.objects.create(
            code="UPDATE-STALE",
            name="Update Stale",
            default_unit="unit",
            created_by=self.admin,
        )
        Product.objects.filter(pk=product.pk).update(version=2)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("catalog:product-update", args=[product.pk]),
            {
                "code": product.code,
                "name": "Stale edit",
                "description": "",
                "default_unit": "unit",
                "expected_version": 1,
            },
        )

        self.assertEqual(response.status_code, 409)
