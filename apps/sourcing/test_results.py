import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.choices import UserRole
from apps.audit.models import AuditEvent
from apps.catalog.models import Product, Supplier
from apps.tender.services import create_tender, get_current_tender_revision

from .calculations import calculate_allocation_purchase
from .choices import ResultSourceType, ResultStatus
from .models import (
    ProcurementResult,
    ProcurementResultSelection,
    SupplierAllocation,
)
from .result_services import (
    create_manual_result,
    customize_result,
    select_result,
    update_draft_result,
    validate_result,
)
from .services import create_supplier_offer, deactivate_supplier_offer

User = get_user_model()


class ProcurementResultFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="result-admin",
            email="result-admin@example.test",
            password="StrongPassword123!",
            full_name="Result Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="result-staff",
            email="result-staff@example.test",
            password="StrongPassword123!",
            full_name="Result Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.product = Product.objects.create(
            code="PUMP-001",
            name="Infusion Pump",
            description="Original product",
            default_unit="unit",
            created_by=cls.admin,
        )
        cls.supplier_a = Supplier.objects.create(
            code="SUP-A",
            name="Supplier A",
            created_by=cls.admin,
        )
        cls.supplier_b = Supplier.objects.create(
            code="SUP-B",
            name="Supplier B",
            created_by=cls.admin,
        )
        cls.offer_a = create_supplier_offer(
            actor=cls.staff,
            supplier_id=cls.supplier_a.pk,
            product_id=cls.product.pk,
            supplier_reference="A-001",
            base_unit_price=Decimal("7000000.0000"),
            discount_percent=Decimal("10.0000"),
            available_quantity=Decimal("60.000"),
            valid_from=date(2026, 1, 1),
            valid_until=date(2030, 12, 31),
            correlation_id=str(uuid.uuid4()),
        )
        cls.offer_b = create_supplier_offer(
            actor=cls.staff,
            supplier_id=cls.supplier_b.pk,
            product_id=cls.product.pk,
            supplier_reference="B-001",
            base_unit_price=Decimal("7500000.0000"),
            discount_percent=Decimal("5.0000"),
            available_quantity=Decimal("100.000"),
            valid_from=date(2026, 1, 1),
            valid_until=date(2030, 12, 31),
            correlation_id=str(uuid.uuid4()),
        )
        tender = create_tender(
            actor=cls.staff,
            internal_code="TND-RESULT-001",
            tender_reference_number="RS-RESULT-001",
            institution_name="Rumah Sakit Demo",
            institution_address="Jakarta",
            title="Pengadaan Infusion Pump",
            description="Result fixture",
            total_hps=Decimal("800000000.00"),
            items=[
                {
                    "line_number": 1,
                    "product_id": cls.product.pk,
                    "requested_quantity": Decimal("100.000"),
                    "unit": "unit",
                    "specification": "Medical grade",
                    "description": "",
                }
            ],
            correlation_id=str(uuid.uuid4()),
        )
        cls.revision = get_current_tender_revision(tender.pk)
        cls.tender_item = cls.revision.items.get()

    def correlation_id(self):
        return str(uuid.uuid4())

    def allocations(self, quantity_a="60.000", quantity_b="40.000"):
        return [
            {
                "tender_item_id": self.tender_item.pk,
                "line_number": 1,
                "supplier_offer_id": self.offer_a.pk,
                "allocated_quantity": Decimal(quantity_a),
            },
            {
                "tender_item_id": self.tender_item.pk,
                "line_number": 2,
                "supplier_offer_id": self.offer_b.pk,
                "allocated_quantity": Decimal(quantity_b),
            },
        ]

    def create_draft(self, allocations=None):
        return create_manual_result(
            actor=self.staff,
            tender_revision_id=self.revision.pk,
            allocations=(
                self.allocations() if allocations is None else allocations
            ),
            correlation_id=self.correlation_id(),
        )

    def create_valid(self, allocations=None):
        result = self.create_draft(allocations)
        return validate_result(
            actor=self.staff,
            result_id=result.pk,
            expected_version=result.version,
            correlation_id=self.correlation_id(),
        )


class ProcurementCalculationTests(TestCase):
    def test_allocation_uses_half_up_rounding(self):
        self.assertEqual(
            calculate_allocation_purchase("1.000", "10.0050"),
            Decimal("10.01"),
        )


class ProcurementResultServiceTests(
    ProcurementResultFixtureMixin, TestCase
):
    def test_golden_result_validates_with_snapshot_hash_and_audit(self):
        result = self.create_draft()

        validated = validate_result(
            actor=self.staff,
            result_id=result.pk,
            expected_version=1,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(validated.status, ResultStatus.VALID)
        self.assertEqual(validated.total_purchase, Decimal("663000000.00"))
        self.assertEqual(validated.version, 2)
        self.assertEqual(len(validated.result_hash), 64)
        self.assertEqual(
            validated.result_snapshot["data"]["total_purchase"],
            "663000000.00",
        )
        item = validated.items.get()
        self.assertEqual(item.item_purchase_total, Decimal("663000000.00"))
        self.assertSetEqual(
            set(
                item.allocations.values_list(
                    "allocation_purchase", flat=True
                )
            ),
            {Decimal("378000000.00"), Decimal("285000000.00")},
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="RESULT_CREATED").exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="RESULT_VALIDATED").exists()
        )

    def test_incomplete_draft_cannot_be_validated(self):
        result = self.create_draft(self.allocations()[:1])

        with self.assertRaisesMessage(
            ValidationError, "QUANTITY_NOT_FULFILLED"
        ):
            validate_result(
                actor=self.staff,
                result_id=result.pk,
                expected_version=1,
                correlation_id=self.correlation_id(),
            )

        result.refresh_from_db()
        self.assertEqual(result.status, ResultStatus.DRAFT)
        self.assertIsNone(result.total_purchase)

    def test_offer_deactivated_after_draft_is_rejected_on_validation(self):
        result = self.create_draft()
        deactivate_supplier_offer(
            actor=self.staff,
            offer_id=self.offer_a.pk,
            expected_version=self.offer_a.version,
            correlation_id=self.correlation_id(),
        )

        with self.assertRaisesMessage(ValidationError, "OFFER_INACTIVE"):
            validate_result(
                actor=self.staff,
                result_id=result.pk,
                expected_version=result.version,
                correlation_id=self.correlation_id(),
            )

    def test_corrupt_price_snapshot_is_rejected_on_validation(self):
        result = self.create_draft()
        allocation = SupplierAllocation.objects.filter(
            supplier_offer=self.offer_a
        )
        allocation.update(net_purchase_price_snapshot=Decimal("1.0000"))

        with self.assertRaisesMessage(
            ValidationError, "CALCULATION_MISMATCH"
        ):
            validate_result(
                actor=self.staff,
                result_id=result.pk,
                expected_version=result.version,
                correlation_id=self.correlation_id(),
            )

    def test_offer_product_mismatch_is_rejected_on_draft_creation(self):
        other_product = Product.objects.create(
            code="OTHER-001",
            name="Other Product",
            default_unit="unit",
            created_by=self.admin,
        )
        other_offer = create_supplier_offer(
            actor=self.staff,
            supplier_id=self.supplier_a.pk,
            product_id=other_product.pk,
            supplier_reference="OTHER",
            base_unit_price=Decimal("100.0000"),
            discount_percent=Decimal("0.0000"),
            available_quantity=None,
            valid_from=None,
            valid_until=None,
            correlation_id=self.correlation_id(),
        )
        allocations = self.allocations()
        allocations[0]["supplier_offer_id"] = other_offer.pk

        with self.assertRaisesMessage(
            ValidationError, "Produk offer tidak sesuai"
        ):
            self.create_draft(allocations)

    def test_offer_limit_is_scoped_to_each_result(self):
        first = self.create_valid()
        second = self.create_valid()

        self.assertEqual(first.total_purchase, second.total_purchase)
        self.assertEqual(ProcurementResult.objects.count(), 2)

    def test_offer_limit_is_aggregated_inside_one_result(self):
        tender = create_tender(
            actor=self.staff,
            internal_code="TND-TWO-LINES",
            tender_reference_number="",
            institution_name="Rumah Sakit Demo",
            institution_address="",
            title="Dua baris produk sama",
            description="",
            total_hps=None,
            items=[
                {
                    "line_number": line,
                    "product_id": self.product.pk,
                    "requested_quantity": Decimal("40.000"),
                    "unit": "unit",
                    "specification": "",
                    "description": "",
                }
                for line in (1, 2)
            ],
            correlation_id=self.correlation_id(),
        )
        revision = get_current_tender_revision(tender.pk)
        items = list(revision.items.all())
        allocations = [
            {
                "tender_item_id": item.pk,
                "line_number": 1,
                "supplier_offer_id": self.offer_a.pk,
                "allocated_quantity": Decimal("40.000"),
            }
            for item in items
        ]

        with self.assertRaisesMessage(
            ValidationError, "melebihi jumlah tersedia"
        ):
            create_manual_result(
                actor=self.staff,
                tender_revision_id=revision.pk,
                allocations=allocations,
                correlation_id=self.correlation_id(),
            )

    def test_update_replaces_children_and_rejects_stale_version(self):
        result = self.create_draft(self.allocations("50.000", "40.000"))
        updated = update_draft_result(
            actor=self.staff,
            result_id=result.pk,
            expected_version=1,
            allocations=self.allocations(),
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(updated.version, 2)
        self.assertEqual(SupplierAllocation.objects.count(), 2)
        with self.assertRaises(ValidationError):
            update_draft_result(
                actor=self.staff,
                result_id=result.pk,
                expected_version=1,
                allocations=self.allocations(),
                correlation_id=self.correlation_id(),
            )

    def test_valid_result_and_children_are_immutable(self):
        result = self.create_draft()
        item = result.items.get()
        allocation = item.allocations.first()
        validate_result(
            actor=self.staff,
            result_id=result.pk,
            expected_version=result.version,
            correlation_id=self.correlation_id(),
        )
        result.refresh_from_db()

        result.total_purchase = Decimal("1.00")
        with self.assertRaises(ValidationError):
            result.save()
        with self.assertRaises(ValidationError):
            ProcurementResult.objects.filter(pk=result.pk).update(version=3)
        item.line_number = 9
        with self.assertRaises(ValidationError):
            item.save()
        with self.assertRaises(ValidationError):
            allocation.delete()

    def test_customization_preserves_source_and_same_cost(self):
        source = self.create_valid()
        customized = customize_result(
            actor=self.staff,
            source_result_id=source.pk,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(
            customized.source_type, ResultSourceType.CUSTOMIZED
        )
        self.assertEqual(customized.source_result, source)
        self.assertEqual(customized.status, ResultStatus.DRAFT)
        validated = validate_result(
            actor=self.staff,
            result_id=customized.pk,
            expected_version=1,
            correlation_id=self.correlation_id(),
        )
        self.assertEqual(validated.total_purchase, source.total_purchase)
        source.refresh_from_db()
        self.assertEqual(source.status, ResultStatus.VALID)

    def test_selection_is_sequenced_and_current_idempotent(self):
        first_result = self.create_valid()
        second_result = self.create_valid()

        first = select_result(
            actor=self.staff,
            result_id=first_result.pk,
            correlation_id=self.correlation_id(),
        )
        duplicate = select_result(
            actor=self.staff,
            result_id=first_result.pk,
            correlation_id=self.correlation_id(),
        )
        second = select_result(
            actor=self.staff,
            result_id=second_result.pk,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(first.pk, duplicate.pk)
        self.assertEqual(second.selection_number, 2)
        self.assertEqual(ProcurementResultSelection.objects.count(), 2)
        with self.assertRaises(ValidationError):
            first.delete()

    def test_draft_cannot_be_selected(self):
        result = self.create_draft()
        with self.assertRaisesMessage(ValidationError, "VALID"):
            select_result(
                actor=self.staff,
                result_id=result.pk,
                correlation_id=self.correlation_id(),
            )

    def test_result_snapshot_survives_master_rename(self):
        result = self.create_valid()
        original_snapshot = result.result_snapshot
        self.product.name = "Renamed Product"
        self.product.save(update_fields=["name"])
        self.supplier_a.name = "Renamed Supplier"
        self.supplier_a.save(update_fields=["name"])

        result.refresh_from_db()
        self.assertEqual(result.result_snapshot, original_snapshot)
        allocations = result.result_snapshot["data"]["items"][0][
            "allocations"
        ]
        self.assertEqual(allocations[0]["supplier"]["name"], "Supplier A")

    def test_admin_cannot_create_result(self):
        with self.assertRaises(PermissionDenied):
            create_manual_result(
                actor=self.admin,
                tender_revision_id=self.revision.pk,
                allocations=self.allocations(),
                correlation_id=self.correlation_id(),
            )


class ProcurementResultViewTests(
    ProcurementResultFixtureMixin, TestCase
):
    def form_payload(self):
        return {
            "tender_revision": str(self.revision.pk),
            "allocations-TOTAL_FORMS": "2",
            "allocations-INITIAL_FORMS": "0",
            "allocations-MIN_NUM_FORMS": "0",
            "allocations-MAX_NUM_FORMS": "1000",
            "allocations-0-tender_item": str(self.tender_item.pk),
            "allocations-0-line_number": "1",
            "allocations-0-supplier_offer": str(self.offer_a.pk),
            "allocations-0-allocated_quantity": "60.000",
            "allocations-1-tender_item": str(self.tender_item.pk),
            "allocations-1-line_number": "2",
            "allocations-1-supplier_offer": str(self.offer_b.pk),
            "allocations-1-allocated_quantity": "40.000",
        }

    def test_only_staff_can_open_result_list(self):
        url = reverse("sourcing:result-list")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_result_create_uses_revision_selection_step(self):
        self.client.force_login(self.staff)

        selection = self.client.get(reverse("sourcing:result-create"))
        allocations = self.client.get(
            reverse("sourcing:result-create"),
            {"tender_revision": self.revision.pk},
        )

        self.assertContains(selection, "Lanjutkan")
        self.assertNotContains(selection, "Supplier allocation")
        self.assertContains(allocations, "Supplier allocation")
        self.assertContains(allocations, self.offer_a.supplier.code)

    def test_staff_can_create_validate_and_select_result(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sourcing:result-create"), self.form_payload()
        )
        result = ProcurementResult.objects.get()
        self.assertRedirects(
            response,
            reverse("sourcing:result-detail", args=[result.pk]),
        )

        response = self.client.post(
            reverse("sourcing:result-validate", args=[result.pk]),
            {"expected_version": 1},
        )
        self.assertRedirects(
            response,
            reverse("sourcing:result-detail", args=[result.pk]),
        )
        result.refresh_from_db()
        self.assertEqual(result.status, ResultStatus.VALID)

        response = self.client.post(
            reverse("sourcing:result-select", args=[result.pk])
        )
        self.assertRedirects(
            response,
            reverse("sourcing:result-detail", args=[result.pk]),
        )
        self.assertTrue(result.selections.exists())

    def test_result_detail_uses_snapshot_values(self):
        result = self.create_valid()
        self.supplier_a.name = "Renamed Supplier"
        self.supplier_a.save(update_fields=["name"])
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("sourcing:result-detail", args=[result.pk])
        )

        self.assertContains(response, "Supplier A")
        self.assertNotContains(response, "Renamed Supplier")

    def test_update_returns_conflict_for_stale_version(self):
        result = self.create_draft()
        ProcurementResult.objects.filter(pk=result.pk).update(version=2)
        payload = self.form_payload()
        payload.pop("tender_revision")
        payload["expected_version"] = "1"
        payload["allocations-INITIAL_FORMS"] = "2"
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("sourcing:result-update", args=[result.pk]), payload
        )

        self.assertEqual(response.status_code, 409)


class ProcurementSelectionConcurrencyTests(
    ProcurementResultFixtureMixin, TransactionTestCase
):
    reset_sequences = True

    def setUp(self):
        type(self).setUpTestData()

    def _select_in_thread(self, result_id):
        close_old_connections()
        try:
            actor = User.objects.get(pk=self.staff.pk)
            return select_result(
                actor=actor,
                result_id=result_id,
                correlation_id=self.correlation_id(),
            ).selection_number
        finally:
            close_old_connections()

    def test_concurrent_selection_has_unique_monotonic_sequence(self):
        first_result = self.create_valid()
        second_result = self.create_valid()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._select_in_thread, result.pk)
                for result in (first_result, second_result)
            ]
            numbers = {future.result() for future in futures}

        self.assertSetEqual(numbers, {1, 2})
        self.assertSetEqual(
            set(
                ProcurementResultSelection.objects.values_list(
                    "selection_number", flat=True
                )
            ),
            {1, 2},
        )
