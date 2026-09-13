"""Normalisasi identifier bisnis lintas bounded context."""


def normalize_business_code(value):
    """Kembalikan representasi canonical kode bisnis."""

    if not isinstance(value, str):
        return value
    return value.strip().upper()
