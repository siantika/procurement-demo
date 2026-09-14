import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.choices import UserRole
from apps.approval.services import approve_bid, reject_bid
from apps.audit.models import AuditEvent
from apps.catalog.models import Product, Supplier
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.notifications.models import Notification
from apps.sourcing.models import ProcurementResultSelection
from apps.sourcing.result_services import (
    create_manual_result,
    select_result,
    validate_result,
)
from apps.sourcing.services import create_supplier_offer
from apps.tender.services import create_tender, get_current_tender_revision

from .calculations import calculate_bid_pricing
from .choices import BidStatus
from .models import BidProposal, BidProposalRevision
from .services import (
    create_bid_proposal,
    revise_rejected_bid,
    set_target_margin,
    submit_bid,
)

User = get_user_model()


class BidFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="bid-admin",
            email="bid-admin@example.test",
            password="StrongPassword123!",
            full_name="Bid Admin",
            role=UserRole.ADMIN,
        )
        cls.staff = User.objects.create_user(
            username="bid-staff",
            email="bid-staff@example.test",
            password="StrongPassword123!",
            full_name="Bid Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )
        cls.manager = User.objects.create_user(
            username="bid-manager",
            email="bid-manager@example.test",
            password="StrongPassword123!",
            full_name="Bid Manager",
            role=UserRole.MANAGER,
        )
        cls.product = Product.objects.create(
            code="BID-PUMP",
            name="Infusion Pump",
            default_unit="unit",
            created_by=cls.admin,
        )
        cls.supplier_a = Supplier.objects.create(
            code="BID-A", name="Supplier A", created_by=cls.admin
        )
        cls.supplier_b = Supplier.objects.create(
            code="BID-B", name="Supplier B", created_by=cls.admin
        )
        cls.offer_a = create_supplier_offer(
            actor=cls.staff,
            supplier_id=cls.supplier_a.pk,
            product_id=cls.product.pk,
            supplier_reference="A",
            base_unit_price=Decimal("7000000.0000"),
            discount_percent=Decimal("10.0000"),
            available_quantity=Decimal("60.000"),
            valid_from=None,
            valid_until=None,
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
            valid_from=None,
            valid_until=None,
            correlation_id=str(uuid.uuid4()),
        )
        cls.tender = create_tender(
            actor=cls.staff,
            internal_code="TND-BID-001",
            tender_reference_number="BID-001",
            institution_name="Rumah Sakit Demo",
            institution_address="Jakarta",
            title="Pengadaan Infusion Pump",
            description="Bid fixture",
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
        cls.revision = get_current_tender_revision(cls.tender.pk)
        cls.tender_item = cls.revision.items.get()

    def correlation_id(self):
        return str(uuid.uuid4())

    def create_selected_result(self):
        result = create_manual_result(
            actor=self.staff,
            tender_revision_id=self.revision.pk,
            allocations=[
                {
                    "tender_item_id": self.tender_item.pk,
                    "line_number": 1,
                    "supplier_offer_id": self.offer_a.pk,
                    "allocated_quantity": Decimal("60.000"),
                },
                {
                    "tender_item_id": self.tender_item.pk,
                    "line_number": 2,
                    "supplier_offer_id": self.offer_b.pk,
                    "allocated_quantity": Decimal("40.000"),
                },
            ],
            correlation_id=self.correlation_id(),
        )
        result = validate_result(
            actor=self.staff,
            result_id=result.pk,
            expected_version=result.version,
            correlation_id=self.correlation_id(),
        )
        select_result(
            actor=self.staff,
            result_id=result.pk,
            correlation_id=self.correlation_id(),
        )
        return result

    def create_bid(self):
        if not ProcurementResultSelection.objects.exists():
            self.create_selected_result()
        return create_bid_proposal(
            actor=self.staff,
            tender_request_id=self.tender.pk,
            correlation_id=self.correlation_id(),
        )

    def priced_bid(self, margin="15.0000"):
        proposal, revision = self.create_bid()
        revision = set_target_margin(
            actor=self.staff,
            revision_id=revision.pk,
            expected_version=revision.version,
            target_margin_percent=Decimal(margin),
            correlation_id=self.correlation_id(),
        )
        return proposal, revision

    def submitted_bid(self):
        proposal, revision = self.priced_bid()
        revision = submit_bid(
            actor=self.staff,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )
        return proposal, revision


class BidCalculationTests(TestCase):
    def test_golden_pricing_and_hps(self):
        pricing = calculate_bid_pricing(
            items=[
                {
                    "tender_item_id": "item-1",
                    "requested_quantity": Decimal("100.000"),
                    "item_purchase_total": Decimal("663000000.00"),
                }
            ],
            target_margin_percent=Decimal("15.0000"),
            total_hps=Decimal("800000000.00"),
        )

        self.assertEqual(pricing.total_bid_value, Decimal("780000000.00"))
        self.assertEqual(pricing.gross_profit, Decimal("117000000.00"))
        self.assertEqual(
            pricing.actual_margin_percent, Decimal("15.0000")
        )
        self.assertEqual(
            pricing.max_margin_percent, Decimal("17.1250")
        )
        self.assertTrue(pricing.is_hps_feasible)

    def test_margin_must_be_bounded(self):
        with self.assertRaises(ValueError):
            calculate_bid_pricing(
                items=[
                    {
                        "tender_item_id": "item-1",
                        "requested_quantity": Decimal("1.000"),
                        "item_purchase_total": Decimal("1.00"),
                    }
                ],
                target_margin_percent=Decimal("100"),
                total_hps=None,
            )


class BidServiceTests(BidFixtureMixin, TestCase):
    def test_bid_requires_selected_result(self):
        with self.assertRaises(InvalidTransition):
            create_bid_proposal(
                actor=self.staff,
                tender_request_id=self.tender.pk,
                correlation_id=self.correlation_id(),
            )

    def test_create_price_and_submit_bid(self):
        proposal, revision = self.submitted_bid()

        self.assertEqual(revision.status, BidStatus.WAITING_APPROVAL)
        self.assertEqual(revision.total_purchase, Decimal("663000000.00"))
        self.assertEqual(revision.total_bid_value, Decimal("780000000.00"))
        self.assertEqual(revision.items.count(), 1)
        self.assertEqual(len(revision.submission_hash), 64)
        self.assertEqual(revision.submitted_by, self.staff)
        self.assertEqual(proposal.current_revision_number, 1)
        self.assertTrue(
            AuditEvent.objects.filter(action="BID_SUBMITTED").exists()
        )
        notification = Notification.objects.get(
            recipient=self.manager,
            type="BID_WAITING_APPROVAL",
        )
        self.assertEqual(notification.source_entity_id, revision.pk)

    def test_submitted_bid_appears_as_manager_toast(self):
        _proposal, revision = self.submitted_bid()
        self.client.force_login(self.manager)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Bid menunggu persetujuan")
        self.assertContains(response, str(revision.pk))

    def test_non_feasible_bid_cannot_be_submitted(self):
        _proposal, revision = self.priced_bid("20.0000")

        self.assertFalse(revision.is_hps_feasible)
        with self.assertRaises(InvalidTransition):
            submit_bid(
                actor=self.staff,
                revision_id=revision.pk,
                expected_version=revision.version,
                correlation_id=self.correlation_id(),
            )

    def test_stale_pricing_version_is_rejected(self):
        _proposal, revision = self.priced_bid()

        with self.assertRaises(ConcurrencyConflict):
            set_target_margin(
                actor=self.staff,
                revision_id=revision.pk,
                expected_version=1,
                target_margin_percent=Decimal("10.0000"),
                correlation_id=self.correlation_id(),
            )

    def test_only_staff_can_create_bid(self):
        self.create_selected_result()
        with self.assertRaises(PermissionDenied):
            create_bid_proposal(
                actor=self.manager,
                tender_request_id=self.tender.pk,
                correlation_id=self.correlation_id(),
            )

    def test_rejected_bid_creates_notification_and_new_revision(self):
        proposal, revision = self.submitted_bid()
        decision = reject_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            reason="Margin perlu diturunkan.",
            correlation_id=self.correlation_id(),
        )
        proposal.refresh_from_db()
        new_revision = revise_rejected_bid(
            actor=self.staff,
            proposal_id=proposal.pk,
            expected_version=proposal.version,
            correlation_id=self.correlation_id(),
        )

        revision.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.REJECTED)
        self.assertEqual(decision.reason, "Margin perlu diturunkan.")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.staff,
                type="BID_REJECTED",
            ).exists()
        )
        self.assertEqual(new_revision.status, BidStatus.DRAFT)
        self.assertEqual(new_revision.revision_number, 2)
        self.assertEqual(proposal.current_revision_number, 2)
        self.assertEqual(BidProposalRevision.objects.count(), 2)

    def test_approve_marks_all_manager_notifications_read(self):
        other_manager = User.objects.create_user(
            username="bid-manager-secondary",
            email="bid-manager-secondary@example.test",
            password="StrongPassword123!",
            full_name="Bid Manager Secondary",
            role=UserRole.MANAGER,
        )
        _proposal, revision = self.submitted_bid()

        self.assertEqual(
            Notification.objects.filter(
                recipient__in=[self.manager, other_manager],
                type="BID_WAITING_APPROVAL",
                read_at__isnull=True,
            ).count(),
            2,
        )

        approve_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )

        revision.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.APPROVED)
        self.assertFalse(
            Notification.objects.filter(
                recipient__in=[self.manager, other_manager],
                type="BID_WAITING_APPROVAL",
                read_at__isnull=True,
            ).exists()
        )

    def test_approve_notifies_submitting_staff(self):
        _proposal, revision = self.submitted_bid()

        approve_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )

        notification = Notification.objects.get(
            recipient=self.staff,
            type="BID_APPROVED",
        )
        self.assertEqual(notification.source_entity_id, revision.pk)
        self.assertIn(
            revision.bid_proposal.proposal_number,
            notification.message,
        )

    def test_reject_requires_reason(self):
        _proposal, revision = self.submitted_bid()

        with self.assertRaises(ValidationError):
            reject_bid(
                actor=self.manager,
                revision_id=revision.pk,
                expected_version=revision.version,
                reason="  ",
                correlation_id=self.correlation_id(),
            )

    def test_only_manager_can_decide(self):
        _proposal, revision = self.submitted_bid()

        with self.assertRaises(PermissionDenied):
            approve_bid(
                actor=self.staff,
                revision_id=revision.pk,
                expected_version=revision.version,
                correlation_id=self.correlation_id(),
            )

    def test_submitted_revision_and_items_are_immutable(self):
        _proposal, revision = self.submitted_bid()

        revision.total_bid_value = Decimal("1.00")
        with self.assertRaises(ValidationError):
            revision.save()
        with self.assertRaises(ValidationError):
            BidProposalRevision.objects.filter(pk=revision.pk).update(
                total_bid_value=Decimal("1.00")
            )
        with self.assertRaises(ValidationError):
            revision.items.update(item_bid_total=Decimal("1.00"))


class BidViewTests(BidFixtureMixin, TestCase):
    def test_staff_can_create_price_and_submit_from_ui(self):
        self.create_selected_result()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("bids:create", kwargs={"tender_id": self.tender.pk})
        )
        proposal = BidProposal.objects.get()
        self.assertRedirects(
            response,
            reverse("bids:detail", kwargs={"proposal_id": proposal.pk}),
        )
        revision = proposal.revisions.get()
        response = self.client.post(
            reverse("bids:price", kwargs={"proposal_id": proposal.pk}),
            {
                "expected_version": revision.version,
                "target_margin_percent": "15.0000",
            },
        )
        self.assertEqual(response.status_code, 302)
        revision.refresh_from_db()
        response = self.client.post(
            reverse("bids:submit", kwargs={"proposal_id": proposal.pk}),
            {"expected_version": revision.version},
        )
        self.assertEqual(response.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.WAITING_APPROVAL)

    def test_manager_sees_submitted_bid_in_queue(self):
        proposal, revision = self.submitted_bid()
        self.client.force_login(self.manager)

        response = self.client.get(reverse("approval:queue"))

        self.assertContains(response, proposal.proposal_number)

        detail = self.client.get(
            reverse("bids:detail", kwargs={"proposal_id": proposal.pk})
        )
        self.assertContains(detail, "Setujui Bid")
        reject_form = self.client.get(
            reverse(
                "approval:reject-form",
                kwargs={"revision_id": revision.pk},
            )
        )
        self.assertContains(reject_form, "Alasan penolakan")

    def test_bid_detail_uses_consistent_display_format(self):
        proposal, _revision = self.submitted_bid()
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("bids:detail", kwargs={"proposal_id": proposal.pk})
        )

        self.assertContains(response, "Rp780.000.000,00")
        self.assertContains(response, "100 unit")
        self.assertNotContains(response, "100.000 unit")

    def test_approved_bid_emphasizes_manager_decision(self):
        proposal, revision = self.submitted_bid()
        approve_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("bids:detail", kwargs={"proposal_id": proposal.pk})
        )

        self.assertContains(response, "Persetujuan Manager")
        self.assertContains(response, "Bid telah disetujui")
        self.assertContains(response, "Tandatangani Bid")

    def test_success_message_uses_success_alert(self):
        self.create_selected_result()
        self.client.force_login(self.staff)
        self.client.post(
            reverse("bids:create", kwargs={"tender_id": self.tender.pk})
        )
        proposal = BidProposal.objects.get()
        revision = proposal.revisions.get()

        response = self.client.post(
            reverse("bids:price", kwargs={"proposal_id": proposal.pk}),
            {
                "expected_version": revision.version,
                "target_margin_percent": "15.0000",
            },
            follow=True,
        )

        self.assertContains(response, 'class="alert alert-success"')
