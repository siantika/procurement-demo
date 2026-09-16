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


@register.filter
def status_class(value):
    """Map controlled workflow values to a stable visual state."""

    normalized = str(value or "").upper()
    mapping = {
        "DRAFT": "status-draft",
        "PENDING": "status-review",
        "RUNNING": "status-review",
        "WAITING_APPROVAL": "status-review",
        "VALID": "status-approved",
        "APPROVED": "status-approved",
        "COMPLETED": "status-approved",
        "ACTIVE": "status-approved",
        "ELIGIBLE": "status-approved",
        "SELECTED": "status-approved",
        "SIGNED": "status-signed",
        "FINALIZED": "status-finalized",
        "REJECTED": "status-rejected",
        "FAILED": "status-rejected",
        "INACTIVE": "status-rejected",
        "INELIGIBLE": "status-rejected",
    }
    return mapping.get(normalized, "status-draft")
