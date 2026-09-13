import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.choices import UserRole
from apps.audit.models import AuditEvent
from apps.catalog.models import Product

from .models import TenderRequest, TenderRequestItem, TenderRequestRevision
from .services import (
    create_tender,
    get_current_tender_revision,
    revise_tender,
)

User = get_user_model()


class TenderFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="tender-admin",
            email="tender-admin@example.test",
            password="StrongPassword123!",
            full_name="Tender Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="tender-staff",
            email="tender-staff@example.test",
            password="StrongPassword123!",
            full_name="Tender Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.product = Product.objects.create(
            code="PUMP-001",
            name="Infusion Pump",
            description="Original description",
            default_unit="unit",
            created_by=cls.admin,
        )

    def correlation_id(self):
        return str(uuid.uuid4())

    def revision_values(self, **overrides):
        values = {
            "tender_reference_number": "RS-2026-001",
            "institution_name": "Rumah Sakit Demo",
            "institution_address": "Jakarta",
            "title": "Pengadaan Infusion Pump",
            "description": "Demo",
            "total_hps": Decimal("800000000.00"),
        }
        values.update(overrides)
        return values

    def items(self, **overrides):
        item = {
            "line_number": 1,
            "product_id": self.product.pk,
            "requested_quantity": Decimal("100.000"),
            "unit": "unit",
            "specification": "Medical grade",
            "description": "",
        }
        item.update(overrides)
        return [item]

    def create(self):
        return create_tender(
            actor=self.staff,
            internal_code="TND-2026-001",
            items=self.items(),
            correlation_id=self.correlation_id(),
            **self.revision_values(),
        )


class TenderServiceTests(TenderFixtureMixin, TestCase):

    def test_staff_creates_tender_revision_item_snapshot_and_audit(self):
        tender = self.create()
        revision = get_current_tender_revision(tender.pk)
        item = revision.items.get()

        self.assertEqual(revision.revision_number, 1)
        self.assertEqual(len(revision.content_hash), 64)
        self.assertEqual(item.product_snapshot["name"], "Infusion Pump")
        self.assertTrue(item.product_snapshot["is_active_at_capture"])
        self.assertTrue(
            AuditEvent.objects.filter(action="TENDER_CREATED").exists()
        )

    def test_internal_code_is_normalized(self):
        tender = create_tender(
            actor=self.staff,
            internal_code=" tnd-mixed-001 ",
            items=self.items(),
            correlation_id=self.correlation_id(),
            **self.revision_values(),
        )

        self.assertEqual(tender.internal_code, "TND-MIXED-001")

        with self.assertRaises(ValidationError):
            create_tender(
                actor=self.staff,
                internal_code="tnd-mixed-001",
                items=self.items(),
                correlation_id=self.correlation_id(),
                **self.revision_values(),
            )

    def test_non_staff_cannot_create_tender(self):
        with self.assertRaises(PermissionDenied):
            create_tender(
                actor=self.admin,
                internal_code="FORBIDDEN",
                items=self.items(),
                correlation_id=self.correlation_id(),
                **self.revision_values(),
            )

    def test_requires_item_positive_quantity_and_active_product(self):
        invalid_items = ([], self.items(requested_quantity=Decimal("0")))
        for items in invalid_items:
            with (
                self.subTest(items=items),
                self.assertRaises(ValidationError),
            ):
                create_tender(
                    actor=self.staff,
                    internal_code=str(uuid.uuid4()),
                    items=items,
                    correlation_id=self.correlation_id(),
                    **self.revision_values(),
                )
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            create_tender(
                actor=self.staff,
                internal_code="INACTIVE-PRODUCT",
                items=self.items(),
                correlation_id=self.correlation_id(),
                **self.revision_values(),
            )

    def test_revision_preserves_historical_content(self):
        tender = self.create()
        original = get_current_tender_revision(tender.pk)
        original_hash = original.content_hash
        self.product.name = "Renamed Product"
        self.product.save(update_fields=["name"])

        revised = revise_tender(
            actor=self.staff,
            tender_id=tender.pk,
            expected_version=tender.version,
            items=self.items(requested_quantity=Decimal("120.000")),
            correlation_id=self.correlation_id(),
            **self.revision_values(revision_reason="Quantity berubah"),
        )

        original.refresh_from_db()
        self.assertEqual(original.content_hash, original_hash)
        self.assertEqual(
            original.items.get().product_snapshot["name"], "Infusion Pump"
        )
        self.assertEqual(
            revised.items.get().product_snapshot["name"], "Renamed Product"
        )
        tender.refresh_from_db()
        self.assertEqual(tender.current_revision_number, 2)
        self.assertEqual(tender.version, 2)

    def test_revision_rows_are_immutable(self):
        tender = self.create()
        revision = get_current_tender_revision(tender.pk)
        revision.title = "Changed"
        with self.assertRaises(ValidationError):
            revision.save()
        with self.assertRaises(ValidationError):
            TenderRequestRevision.objects.filter(pk=revision.pk).update(
                title="Changed"
            )
        item = revision.items.get()
        with self.assertRaises(ValidationError):
            item.delete()

    def test_revision_rejects_stale_version_and_missing_reason(self):
        tender = self.create()
        for expected_version, reason in ((0, "Changed"), (1, "")):
            with (
                self.subTest(
                    expected_version=expected_version, reason=reason
                ),
                self.assertRaises(ValidationError),
            ):
                revise_tender(
                    actor=self.staff,
                    tender_id=tender.pk,
                    expected_version=expected_version,
                    items=self.items(),
                    correlation_id=self.correlation_id(),
                    **self.revision_values(revision_reason=reason),
                )

    def test_database_prevents_duplicate_lines(self):
        tender = self.create()
        revision = get_current_tender_revision(tender.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TenderRequestItem.objects.create(
                tender_revision=revision,
                line_number=1,
                product=self.product,
                product_snapshot={},
                requested_quantity=1,
                unit="unit",
            )


class TenderViewTests(TenderFixtureMixin, TestCase):
    def test_only_staff_can_open_tender_list(self):
        url = reverse("tender:list")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_create_tender_through_formset(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("tender:create"),
            {
                "internal_code": "TND-UI-001",
                "tender_reference_number": "REF-UI",
                "institution_name": "RS UI",
                "institution_address": "Jakarta",
                "title": "Tender UI",
                "description": "",
                "total_hps": "800000000.00",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-line_number": "1",
                "items-0-product": str(self.product.pk),
                "items-0-requested_quantity": "100.000",
                "items-0-unit": "unit",
                "items-0-specification": "Medical grade",
                "items-0-description": "",
            },
        )

        tender = TenderRequest.objects.get(internal_code="TND-UI-001")
        self.assertRedirects(
            response,
            reverse("tender:detail", args=[tender.pk]),
        )

    def test_revision_returns_conflict_for_stale_form(self):
        tender = self.create()
        TenderRequest.objects.filter(pk=tender.pk).update(version=2)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("tender:revise", args=[tender.pk]),
            {
                "internal_code": tender.internal_code,
                "expected_version": "1",
                "tender_reference_number": "RS-2026-001",
                "institution_name": "Rumah Sakit Demo",
                "institution_address": "Jakarta",
                "title": "Pengadaan Infusion Pump",
                "description": "Demo",
                "total_hps": "800000000.00",
                "revision_reason": "Perubahan stale",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-line_number": "1",
                "items-0-product": str(self.product.pk),
                "items-0-requested_quantity": "101.000",
                "items-0-unit": "unit",
                "items-0-specification": "Medical grade",
                "items-0-description": "",
            },
        )

        self.assertEqual(
            response.status_code,
            409,
            (
                response.context["form"].errors,
                response.context["formset"].errors,
                response.context["formset"].non_form_errors(),
            ),
        )
