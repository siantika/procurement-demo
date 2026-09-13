from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from apps.sourcing.calculations import round_money

CALCULATION_VERSION = "calc-v1"
PRICE_SCALE = Decimal("0.0001")
PERCENT_SCALE = Decimal("0.0001")


@dataclass(frozen=True)
class BidItemPricing:
    tender_item_id: str
    item_purchase_total: Decimal
    unit_purchase_cost: Decimal
    bid_unit_price: Decimal
    item_bid_total: Decimal


@dataclass(frozen=True)
class BidPricing:
    target_margin_percent: Decimal
    total_purchase: Decimal
    total_bid_value: Decimal
    gross_profit: Decimal
    actual_margin_percent: Decimal
    max_margin_percent: Decimal | None
    is_hps_feasible: bool | None
    items: tuple[BidItemPricing, ...]


def normalize_percent(value):
    return Decimal(value).quantize(PERCENT_SCALE, rounding=ROUND_HALF_UP)


def _price(value):
    return Decimal(value).quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)


def calculate_bid_pricing(*, items, target_margin_percent, total_hps):
    margin = normalize_percent(target_margin_percent)
    if margin < 0 or margin >= 100:
        raise ValueError(
            "Target margin harus antara 0 dan kurang dari 100%."
        )
    raw_items = tuple(items)
    if not raw_items:
        raise ValueError("Bid harus memiliki minimal satu item.")

    priced_items = []
    with localcontext() as context:
        context.prec = 38
        denominator = Decimal("1") - (margin / Decimal("100"))
        for item in raw_items:
            purchase = round_money(item["item_purchase_total"])
            quantity = Decimal(item["requested_quantity"])
            if purchase <= 0 or quantity <= 0:
                raise ValueError(
                    "Nilai purchase dan quantity harus positif."
                )
            raw_unit_purchase = purchase / quantity
            unit_purchase = _price(raw_unit_purchase)
            bid_unit = _price(raw_unit_purchase / denominator)
            item_bid_total = round_money(quantity * bid_unit)
            priced_items.append(
                BidItemPricing(
                    tender_item_id=str(item["tender_item_id"]),
                    item_purchase_total=purchase,
                    unit_purchase_cost=unit_purchase,
                    bid_unit_price=bid_unit,
                    item_bid_total=item_bid_total,
                )
            )
        total_purchase = sum(
            (item.item_purchase_total for item in priced_items),
            Decimal("0.00"),
        )
        total_bid = sum(
            (item.item_bid_total for item in priced_items), Decimal("0.00")
        )
        if total_bid <= 0:
            raise ValueError("Total nilai bid harus lebih dari nol.")
        gross_profit = round_money(total_bid - total_purchase)
        actual_margin = normalize_percent(
            (gross_profit / total_bid) * Decimal("100")
        )
        if total_hps is None:
            max_margin = None
            feasible = None
        else:
            hps = Decimal(total_hps)
            if hps <= 0:
                raise ValueError("Total HPS harus lebih dari nol.")
            max_margin = normalize_percent(
                ((hps - total_purchase) / hps) * Decimal("100")
            )
            feasible = total_bid <= hps
    return BidPricing(
        target_margin_percent=margin,
        total_purchase=total_purchase,
        total_bid_value=total_bid,
        gross_profit=gross_profit,
        actual_margin_percent=actual_margin,
        max_margin_percent=max_margin,
        is_hps_feasible=feasible,
        items=tuple(priced_items),
    )
