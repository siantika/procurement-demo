"""Pure policies untuk net price dan eligibility Supplier Offer."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

PRICE_SCALE = Decimal("0.0001")
CALCULATION_VERSION = "calc-v1"


@dataclass(frozen=True)
class OfferEligibilityInput:
    """Nilai offer yang dapat dibangun dari model hidup atau snapshot."""

    offer_active: bool
    product_active: bool
    supplier_active: bool
    product_id: str
    currency: str
    net_purchase_price: Decimal
    available_quantity: Decimal | None
    valid_from: date | None
    valid_until: date | None


@dataclass(frozen=True)
class OfferEligibilityResult:
    eligible: bool
    code: str
    message: str


def calculate_net_purchase_price(base_unit_price, discount_percent):
    with localcontext() as context:
        context.prec = 38
        base = Decimal(base_unit_price)
        discount = Decimal(discount_percent)
        value = base - (base * discount / Decimal("100"))
        return value.quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)


def evaluate_offer_eligibility(
    offer, *, as_of_date, product_id=None, currency="IDR"
):
    """Evaluasi deterministik dengan urutan alasan yang stabil."""

    checks = (
        (offer.offer_active, "OFFER_INACTIVE", "Offer nonaktif."),
        (offer.product_active, "PRODUCT_INACTIVE", "Produk nonaktif."),
        (offer.supplier_active, "SUPPLIER_INACTIVE", "Supplier nonaktif."),
        (
            offer.currency == currency,
            "CURRENCY_MISMATCH",
            f"Mata uang harus {currency}.",
        ),
        (
            product_id is None or offer.product_id == str(product_id),
            "PRODUCT_MISMATCH",
            "Produk offer tidak sesuai.",
        ),
        (
            offer.net_purchase_price > 0,
            "NON_POSITIVE_NET_PRICE",
            "Harga net harus lebih dari nol.",
        ),
        (
            offer.available_quantity is None
            or offer.available_quantity > 0,
            "NO_AVAILABLE_QUANTITY",
            "Jumlah tersedia harus lebih dari nol.",
        ),
        (
            offer.valid_from is None or as_of_date >= offer.valid_from,
            "NOT_YET_VALID",
            "Offer belum memasuki masa berlaku.",
        ),
        (
            offer.valid_until is None or as_of_date <= offer.valid_until,
            "EXPIRED",
            "Offer sudah kedaluwarsa.",
        ),
    )
    for passed, code, message in checks:
        if not passed:
            return OfferEligibilityResult(False, code, message)
    return OfferEligibilityResult(True, "ELIGIBLE", "Eligible")
