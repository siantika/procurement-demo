from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from apps.bids.tests import BidFixtureMixin

from .models import ApprovalDecision
from .services import approve_bid, reject_bid

User = get_user_model()


class ApprovalDecisionTests(BidFixtureMixin, TestCase):
    def test_decision_is_immutable(self):
        _proposal, revision = self.submitted_bid()
        decision = approve_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )

        decision.reason = "Tidak boleh berubah"
        with self.assertRaises(ValidationError):
            decision.save()
        with self.assertRaises(ValidationError):
            ApprovalDecision.objects.filter(pk=decision.pk).update(
                reason="Tidak boleh berubah"
            )


class ApprovalConcurrencyTests(BidFixtureMixin, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        type(self).setUpTestData()
        _proposal, self.revision = self.submitted_bid()

    def _decide(self, action):
        close_old_connections()
        try:
            manager = User.objects.get(pk=self.manager.pk)
            revision = type(self.revision).objects.get(pk=self.revision.pk)
            values = {
                "actor": manager,
                "revision_id": revision.pk,
                "expected_version": revision.version,
                "correlation_id": self.correlation_id(),
            }
            if action == "approve":
                approve_bid(**values)
            else:
                reject_bid(reason="Perlu revisi.", **values)
            return "decided"
        except ValidationError:
            return "conflict"
        finally:
            close_old_connections()

    def test_two_concurrent_decisions_create_exactly_one_row(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(self._decide, ("approve", "reject"))
            )

        self.assertCountEqual(outcomes, ["decided", "conflict"])
        self.assertEqual(ApprovalDecision.objects.count(), 1)
