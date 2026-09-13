"""Read-side selectors untuk Supplier Offer."""

from django.apps import apps

from .policies import OfferEligibilityInput, evaluate_offer_eligibility


def offer_eligibility_input(offer):
    return OfferEligibilityInput(
        offer_active=offer.is_active,
        product_active=offer.product.is_active,
        supplier_active=offer.supplier.is_active,
        product_id=str(offer.product_id),
        currency=offer.currency,
        net_purchase_price=offer.net_purchase_price,
        available_quantity=offer.available_quantity,
        valid_from=offer.valid_from,
        valid_until=offer.valid_until,
    )


def evaluate_current_offer(
    offer, *, as_of_date, product_id=None, currency="IDR"
):
    return evaluate_offer_eligibility(
        offer_eligibility_input(offer),
        as_of_date=as_of_date,
        product_id=product_id,
        currency=currency,
    )


def _used_by_optimization_snapshot(offer):
    """Ikuti kontrak JSON M3 bila app Optimization sudah terpasang."""

    try:
        optimization_run = apps.get_model(
            "optimization", "OptimizationRun"
        )
    except LookupError:
        return False
    return optimization_run.objects.filter(
        input_snapshot__contains={
            "data": {
                "eligible_offers": [{"offer_id": str(offer.pk)}]
            }
        }
    ).exists()


def offer_has_historical_reference(offer):
    if hasattr(offer, "superseding_offer"):
        return True
    allocations = getattr(offer, "allocations", None)
    if allocations is not None and allocations.exists():
        return True
    return _used_by_optimization_snapshot(offer)
