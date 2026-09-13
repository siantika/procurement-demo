from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.policies import require_procurement_staff
from apps.core.exceptions import ConcurrencyConflict

from .forms import TenderDetailsForm, TenderItemFormSet, TenderRevisionForm
from .models import TenderRequest
from .services import (
    create_tender,
    get_current_tender_revision,
    revise_tender,
)


def _item_values(formset):
    items = []
    for form in formset.forms:
        if not form.cleaned_data or form.cleaned_data.get("DELETE"):
            continue
        values = form.cleaned_data
        items.append(
            {
                "line_number": values["line_number"],
                "product_id": values["product"].pk,
                "requested_quantity": values["requested_quantity"],
                "unit": values["unit"],
                "specification": values["specification"],
                "description": values["description"],
            }
        )
    return items


def _add_service_error(form, error):
    if hasattr(error, "message_dict"):
        for field, messages in error.message_dict.items():
            target = field if field in form.fields else None
            for message in messages:
                form.add_error(target, message)
    else:
        form.add_error(None, error.messages[0])


def _revision_initial(tender, revision):
    return {
        "internal_code": tender.internal_code,
        "expected_version": tender.version,
        "tender_reference_number": revision.tender_reference_number,
        "institution_name": revision.institution_name,
        "institution_address": revision.institution_address,
        "title": revision.title,
        "description": revision.description,
        "total_hps": revision.total_hps,
    }


def _items_initial(revision):
    return [
        {
            "line_number": item.line_number,
            "product": item.product,
            "requested_quantity": item.requested_quantity,
            "unit": item.unit,
            "specification": item.specification,
            "description": item.description,
        }
        for item in revision.items.select_related("product")
    ]


@login_required
def tender_list(request):
    require_procurement_staff(request.user)
    tenders = TenderRequest.objects.select_related("created_by")
    return render(request, "tender/tender_list.html", {"tenders": tenders})


@login_required
def tender_detail(request, tender_id):
    require_procurement_staff(request.user)
    tender = get_object_or_404(TenderRequest, pk=tender_id)
    current_revision = get_current_tender_revision(tender.pk)
    revisions = tender.revisions.select_related("created_by")
    return render(
        request,
        "tender/tender_detail.html",
        {
            "tender": tender,
            "revision": current_revision,
            "revisions": revisions,
        },
    )


@login_required
def tender_create(request):
    require_procurement_staff(request.user)
    form = TenderDetailsForm(request.POST or None)
    formset = TenderItemFormSet(request.POST or None, prefix="items")
    response_status = 200
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        values = form.cleaned_data.copy()
        internal_code = values.pop("internal_code")
        try:
            tender = create_tender(
                actor=request.user,
                internal_code=internal_code,
                items=_item_values(formset),
                correlation_id=request.correlation_id,
                **values,
            )
        except ValidationError as error:
            _add_service_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("tender:detail", tender_id=tender.pk)
    return render(
        request,
        "tender/tender_form.html",
        {"form": form, "formset": formset, "title": "Catat tender"},
        status=response_status,
    )


@login_required
def tender_revise(request, tender_id):
    require_procurement_staff(request.user)
    tender = get_object_or_404(TenderRequest, pk=tender_id)
    current_revision = get_current_tender_revision(tender.pk)
    form = TenderRevisionForm(
        request.POST or None,
        initial=_revision_initial(tender, current_revision),
    )
    formset = TenderItemFormSet(
        request.POST or None,
        initial=_items_initial(current_revision),
        prefix="items",
    )
    response_status = 200
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        values = form.cleaned_data.copy()
        values.pop("internal_code")
        expected_version = values.pop("expected_version")
        try:
            revise_tender(
                actor=request.user,
                tender_id=tender.pk,
                expected_version=expected_version,
                items=_item_values(formset),
                correlation_id=request.correlation_id,
                **values,
            )
        except ValidationError as error:
            _add_service_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("tender:detail", tender_id=tender.pk)
    return render(
        request,
        "tender/tender_form.html",
        {"form": form, "formset": formset, "title": "Revisi tender"},
        status=response_status,
    )
