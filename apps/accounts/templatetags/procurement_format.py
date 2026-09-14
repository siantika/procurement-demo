from django import template

from apps.core.formatting import (
    format_decimal,
    format_idr,
    format_quantity,
)

register = template.Library()

register.filter("decimal_id", format_decimal)
register.filter("idr", format_idr)
register.filter("quantity", format_quantity)
