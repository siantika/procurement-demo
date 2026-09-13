import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.choices import UserRole
from apps.audit.models import AuditEvent
from apps.catalog.models import Product, Supplier
from apps.core.exceptions import InvalidTransition
from apps.notifications.models import Notification
from apps.sourcing.choices import ResultSourceType, ResultStatus
from apps.sourcing.models import ProcurementResult, SupplierAllocation
from apps.sourcing.services import create_supplier_offer
from apps.tender.services import create_tender

from .choices import OptimizationStatus
from .models import OptimizationRun
from .services import (
    calculate_run_outcome,
    claim_optimization_run,
    complete_optimization_run,
    fail_optimization_run,
    request_optimization,
    retry_optimization,
)
from .tasks import execute_optimization_run

User = get_user_model()


class OptimizationFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="optimization-admin",
            email="optimization-admin@example.test",
            password="StrongPassword123!",
            full_name="Optimization Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="optimization-staff",
            email="optimization-staff@example.test",
            password="StrongPassword123!",
            full_name="Optimization Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.product = Product.objects.create(
            code="OPT-PUMP",
            name="Infusion Pump",
            default_unit="unit",
            created_by=cls.admin,
        )
        cls.supplier_a = Supplier.objects.create(
            code="OPT-A", name="Supplier A", created_by=cls.admin
        )
        cls.supplier_b = Supplier.objects.create(
            code="OPT-B", name="Supplier B", created_by=cls.admin
        )
        cls.offer_a = create_supplier_offer(
            actor=cls.staff,
            supplier_id=cls.supplier_a.pk,
            product_id=cls.product.pk,
            supplier_reference="A",
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
            supplier_reference="B",
            base_unit_price=Decimal("7500000.0000"),
            discount_percent=Decimal("5.0000"),
            available_quantity=Decimal("100.000"),
            valid_from=date(2026, 1, 1),
            valid_until=date(2030, 12, 31),
            correlation_id=str(uuid.uuid4()),
        )
        cls.tender = create_tender(
            actor=cls.staff,
            internal_code="TND-OPT-001",
            tender_reference_number="OPT-001",
            institution_name="Rumah Sakit Demo",
            institution_address="Jakarta",
            title="Pengadaan Infusion Pump",
            description="Optimization fixture",
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

    def correlation_id(self):
        return str(uuid.uuid4())

    def request_run(self):
        return request_optimization(
            actor=self.staff,
            tender_request_id=self.tender.pk,
            correlation_id=self.correlation_id(),
        )

    def complete_run(self):
        run = self.request_run()
        claimed = claim_optimization_run(
            run_id=run.pk, correlation_id=self.correlation_id()
        )
        outcome = calculate_run_outcome(run=claimed)
        return complete_optimization_run(
            run_id=run.pk,
            outcome=outcome,
            correlation_id=self.correlation_id(),
        )


class OptimizationServiceTests(OptimizationFixtureMixin, TestCase):
    def test_run_persists_ranked_valid_results_and_notification(self):
        run = self.complete_run()

        self.assertEqual(run.status, OptimizationStatus.COMPLETED)
        self.assertEqual(run.result_count, 2)
        first = ProcurementResult.objects.get(
            optimization_run=run, rank=1
        )
        self.assertEqual(first.source_type, ResultSourceType.OPTIMIZER)
        self.assertEqual(first.status, ResultStatus.VALID)
        self.assertEqual(first.total_purchase, Decimal("663000000.00"))
        quantities = list(
            SupplierAllocation.objects.filter(
                procurement_result_item__procurement_result=first
            ).values_list("allocated_quantity", flat=True)
        )
        self.assertCountEqual(
            quantities, [Decimal("60.000"), Decimal("40.000")]
        )
        self.assertEqual(Notification.objects.count(), 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="OPTIMIZATION_COMPLETED"
            ).exists()
        )

    def test_only_one_active_run_is_allowed(self):
        self.request_run()

        with self.assertRaises(InvalidTransition):
            self.request_run()

    def test_worker_uses_frozen_snapshot_after_offer_deactivation(self):
        run = self.request_run()
        self.offer_a.is_active = False
        self.offer_a.save(update_fields=["is_active", "updated_at"])
        claimed = claim_optimization_run(
            run_id=run.pk, correlation_id=self.correlation_id()
        )

        completed = complete_optimization_run(
            run_id=run.pk,
            outcome=calculate_run_outcome(run=claimed),
            correlation_id=self.correlation_id(),
        )

        first = ProcurementResult.objects.get(
            optimization_run=completed, rank=1
        )
        self.assertEqual(first.total_purchase, Decimal("663000000.00"))
        allocation = SupplierAllocation.objects.filter(
            procurement_result_item__procurement_result=first,
            supplier_offer=self.offer_a,
        ).get()
        self.assertTrue(allocation.offer_snapshot["offer_id"])

    def test_redelivery_does_not_duplicate_results_or_notifications(self):
        run = self.request_run()

        first = execute_optimization_run.apply(
            args=(str(run.pk), self.correlation_id())
        ).get()
        second = execute_optimization_run.apply(
            args=(str(run.pk), self.correlation_id())
        ).get()

        self.assertTrue(first["claimed"])
        self.assertFalse(second["claimed"])
        self.assertEqual(
            ProcurementResult.objects.filter(optimization_run=run).count(),
            2,
        )
        self.assertEqual(Notification.objects.count(), 1)

    def test_failure_records_safe_error_and_retry_creates_new_run(self):
        run = self.request_run()
        claim_optimization_run(
            run_id=run.pk, correlation_id=self.correlation_id()
        )
        failed = fail_optimization_run(
            run_id=run.pk,
            safe_error_code="OPTIMIZATION_TECHNICAL_ERROR",
            safe_error_message="Optimization tidak dapat diselesaikan.",
            diagnostic_reference="diag-123",
            correlation_id=self.correlation_id(),
        )

        retry = retry_optimization(
            actor=self.staff,
            run_id=failed.pk,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(failed.status, OptimizationStatus.FAILED)
        self.assertEqual(retry.status, OptimizationStatus.PENDING)
        self.assertEqual(retry.retry_of_run, failed)
        self.assertEqual(Notification.objects.count(), 1)

    def test_admin_cannot_request_optimization(self):
        with self.assertRaises(PermissionDenied):
            request_optimization(
                actor=self.admin,
                tender_request_id=self.tender.pk,
                correlation_id=self.correlation_id(),
            )


class OptimizationViewTests(OptimizationFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.staff)

    def test_staff_can_request_and_view_run(self):
        response = self.client.post(
            reverse(
                "optimization:run-create",
                kwargs={"tender_id": self.tender.pk},
            )
        )
        run = OptimizationRun.objects.get()

        self.assertRedirects(
            response,
            reverse("optimization:run-detail", kwargs={"run_id": run.pk}),
        )
        detail = self.client.get(
            reverse("optimization:run-detail", kwargs={"run_id": run.pk})
        )
        self.assertContains(detail, "Optimization Run")

    def test_status_endpoint_returns_minimal_payload(self):
        run = self.request_run()

        response = self.client.get(
            reverse("optimization:run-status", kwargs={"run_id": run.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "PENDING")
        self.assertFalse(response.json()["terminal"])
