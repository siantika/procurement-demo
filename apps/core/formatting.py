"""Consistent Indonesian display formatting for business numbers."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def _as_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _localize(formatted):
    return formatted.translate(str.maketrans({",": ".", ".": ","}))


def format_idr(value):
    """Return an IDR amount with dot grouping and two decimals."""
    number = _as_decimal(value)
    if number is None:
        return ""
    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"Rp{_localize(f'{rounded:,.2f}')}"


def format_quantity(value):
    """Return a grouped quantity with at most three decimals."""
    number = _as_decimal(value)
    if number is None:
        return ""
    rounded = number.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    formatted = _localize(f"{rounded:,.3f}")
    return formatted.rstrip("0").rstrip(",")


def format_decimal(value):
    """Return a grouped decimal with at most four decimal places."""
    number = _as_decimal(value)
    if number is None:
        return ""
    rounded = number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    formatted = _localize(f"{rounded:,.4f}")
    return formatted.rstrip("0").rstrip(",")
