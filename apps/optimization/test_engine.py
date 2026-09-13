from decimal import Decimal

from django.test import SimpleTestCase

from .contracts import OptimizationItem, OptimizationOffer
from .engine import candidate_identifier, optimize


def offer(identifier, supplier, price, capacity=None):
    return OptimizationOffer(
        offer_id=identifier,
        supplier_id=supplier,
        supplier_code=supplier,
        product_id="product-1",
        net_purchase_price=Decimal(price),
        available_quantity=(
            Decimal(capacity) if capacity is not None else None
        ),
    )


class GreedyBoundedOptimizerTests(SimpleTestCase):
    def test_golden_candidate_minimizes_purchase(self):
        item = OptimizationItem(
            tender_item_id="item-1",
            product_id="product-1",
            requested_quantity=Decimal("100.000"),
            offers=(
                offer("offer-b", "SUP-B", "7125000.0000", "100.000"),
                offer("offer-a", "SUP-A", "6300000.0000", "60.000"),
            ),
        )

        outcome = optimize((item,))

        self.assertEqual(
            outcome.candidates[0].total_purchase,
            Decimal("663000000.00"),
        )
        self.assertEqual(
            [
                row.allocated_quantity
                for row in outcome.candidates[0].allocations
            ],
            [Decimal("60.000"), Decimal("40.000")],
        )

    def test_capacity_shortage_is_business_rejection(self):
        item = OptimizationItem(
            tender_item_id="item-1",
            product_id="product-1",
            requested_quantity=Decimal("100.000"),
            offers=(
                offer("offer-a", "SUP-A", "1.0000", "20.000"),
            ),
        )

        outcome = optimize((item,))

        self.assertEqual(outcome.candidates, ())
        self.assertEqual(
            outcome.rejections[0].reason_code, "INSUFFICIENT_CAPACITY"
        )

    def test_tie_break_prefers_fewer_suppliers(self):
        items = (
            OptimizationItem(
                tender_item_id="item-1",
                product_id="product-1",
                requested_quantity=Decimal("1.000"),
                offers=(
                    offer("offer-a", "SUP-A", "10.0000"),
                    offer("offer-b", "SUP-B", "10.0000"),
                ),
            ),
            OptimizationItem(
                tender_item_id="item-2",
                product_id="product-1",
                requested_quantity=Decimal("1.000"),
                offers=(
                    offer("offer-a", "SUP-A", "10.0000"),
                    offer("offer-b", "SUP-B", "10.0000"),
                ),
            ),
        )

        outcome = optimize(items)

        self.assertEqual(outcome.candidates[0].distinct_supplier_count, 1)
        self.assertLessEqual(
            outcome.candidates[0].identifier,
            outcome.candidates[1].identifier,
        )

    def test_candidate_identifier_is_order_independent(self):
        candidate = optimize(
            (
                OptimizationItem(
                    tender_item_id="item-1",
                    product_id="product-1",
                    requested_quantity=Decimal("2.000"),
                    offers=(offer("offer-a", "SUP-A", "1.0000"),),
                ),
            )
        ).candidates[0]

        self.assertEqual(
            candidate.identifier,
            candidate_identifier(reversed(candidate.allocations)),
        )
