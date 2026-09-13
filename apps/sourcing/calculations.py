"""Pure procurement-cost calculations shared by every result source."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

MONEY_SCALE = Decimal("0.01")
QUANTITY_SCALE = Decimal("0.001")
CALCULATION_VERSION = "calc-v1"
ROUNDING_POLICY_VERSION = "idr-half-up-v1"


def normalize_quantity(value):
    return Decimal(value).quantize(QUANTITY_SCALE)


def round_money(value):
    with localcontext() as context:
        context.prec = 38
        return Decimal(value).quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def calculate_allocation_purchase(quantity, net_purchase_price):
    with localcontext() as context:
        context.prec = 38
        amount = Decimal(quantity) * Decimal(net_purchase_price)
        return round_money(amount)


def calculate_item_purchase(allocation_purchases):
    return sum(allocation_purchases, Decimal("0.00"))


def calculate_total_purchase(item_purchases):
    return sum(item_purchases, Decimal("0.00"))
