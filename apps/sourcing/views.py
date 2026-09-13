from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.policies import require_procurement_staff
from apps.core.exceptions import ConcurrencyConflict
from apps.core.forms import ExpectedVersionForm

from .forms import SupplierOfferForm
from .models import SupplierOffer
from .selectors import evaluate_current_offer
from .services import (
    correct_unused_offer,
    create_supplier_offer,
    deactivate_supplier_offer,
    supersede_supplier_offer,
)


def _values(form):
    values = {
        field: form.cleaned_data[field]
        for field in SupplierOfferForm.Meta.fields
    }
    values["supplier_id"] = values.pop("supplier").pk
    values["product_id"] = values.pop("product").pk
    return values


def _add_error(form, error):
    if hasattr(error, "message_dict"):
        for field, messages in error.message_dict.items():
            target = field if field in form.fields else None
            for message in messages:
                form.add_error(target, message)
    else:
        form.add_error(None, error.messages[0])


@login_required
def offer_list(request):
    require_procurement_staff(request.user)
    offers = SupplierOffer.objects.select_related("supplier", "product")
    rows = [
        {
            "offer": offer,
            "eligibility": evaluate_current_offer(
                offer, as_of_date=timezone.localdate()
            ),
        }
        for offer in offers
    ]
    return render(request, "sourcing/offer_list.html", {"rows": rows})


@login_required
def offer_detail(request, offer_id):
    require_procurement_staff(request.user)
    offer = get_object_or_404(
        SupplierOffer.objects.select_related(
            "supplier", "product", "created_by", "supersedes_offer"
        ),
        pk=offer_id,
    )
    return render(
        request,
        "sourcing/offer_detail.html",
        {
            "offer": offer,
            "eligibility": evaluate_current_offer(
                offer, as_of_date=timezone.localdate()
            ),
        },
    )


@login_required
def offer_create(request):
    require_procurement_staff(request.user)
    form = SupplierOfferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_supplier_offer(
                actor=request.user,
                correlation_id=request.correlation_id,
                **_values(form),
            )
        except ValidationError as error:
            _add_error(form, error)
        else:
            return redirect("sourcing:offer-list")
    return render(
        request,
        "sourcing/offer_form.html",
        {"form": form, "title": "Catat supplier offer", "mode": "create"},
    )


@login_required
def offer_update(request, offer_id):
    require_procurement_staff(request.user)
    offer = get_object_or_404(SupplierOffer, pk=offer_id)
    form = SupplierOfferForm(
        request.POST or None, instance=offer, lock_identity=True
    )
    response_status = 200
    if not request.POST:
        form.fields["expected_version"].initial = offer.version
    if request.method == "POST" and form.is_valid():
        try:
            correct_unused_offer(
                actor=request.user,
                offer_id=offer.pk,
                expected_version=form.cleaned_data["expected_version"],
                correlation_id=request.correlation_id,
                **_values(form),
            )
        except ValidationError as error:
            _add_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("sourcing:offer-list")
    return render(
        request,
        "sourcing/offer_form.html",
        {
            "form": form,
            "title": "Koreksi supplier offer",
            "mode": "update",
        },
        status=response_status,
    )


@login_required
def offer_supersede(request, offer_id):
    require_procurement_staff(request.user)
    offer = get_object_or_404(SupplierOffer, pk=offer_id)
    form = SupplierOfferForm(
        request.POST or None, instance=offer, lock_identity=True
    )
    response_status = 200
    if not request.POST:
        form.fields["expected_version"].initial = offer.version
    if request.method == "POST" and form.is_valid():
        try:
            supersede_supplier_offer(
                actor=request.user,
                offer_id=offer.pk,
                expected_version=form.cleaned_data["expected_version"],
                correlation_id=request.correlation_id,
                **_values(form),
            )
        except ValidationError as error:
            _add_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("sourcing:offer-list")
    return render(
        request,
        "sourcing/offer_form.html",
        {
            "form": form,
            "title": "Buat versi offer baru",
            "mode": "supersede",
        },
        status=response_status,
    )


@login_required
@require_POST
def offer_deactivate(request, offer_id):
    require_procurement_staff(request.user)
    form = ExpectedVersionForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Versi data tidak valid.", status=400)
    try:
        deactivate_supplier_offer(
            actor=request.user,
            offer_id=offer_id,
            expected_version=form.cleaned_data["expected_version"],
            correlation_id=request.correlation_id,
        )
    except SupplierOffer.DoesNotExist:
        return HttpResponse("Offer tidak ditemukan.", status=404)
    except ValidationError as error:
        return HttpResponse(error.messages[0], status=409)
    return redirect("sourcing:offer-list")
