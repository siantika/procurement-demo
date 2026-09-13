from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.policies import require_procurement_staff
from apps.core.exceptions import ConcurrencyConflict, InvalidTransition
from apps.core.forms import ExpectedVersionForm

from .choices import ResultStatus
from .forms import (
    ManualResultForm,
    ResultAllocationFormSet,
    SupplierOfferForm,
)
from .models import (
    ProcurementResult,
    ProcurementResultSelection,
    SupplierAllocation,
    SupplierOffer,
)
from .result_services import (
    create_manual_result,
    customize_result,
    select_result,
    update_draft_result,
    validate_result,
)
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


def _add_result_error(form, formset, error):
    if hasattr(error, "message_dict"):
        allocation_errors = error.message_dict.get("allocations", ())
        if allocation_errors:
            formset._non_form_errors = formset.error_class(
                allocation_errors,
                error_class="nonform",
            )
        for field, field_messages in error.message_dict.items():
            if field == "allocations":
                continue
            target = field if field in form.fields else None
            for message in field_messages:
                form.add_error(target, message)
    else:
        form.add_error(None, error.messages[0])


def _allocation_values(formset):
    values = []
    for form in formset.forms:
        if not form.cleaned_data or form.cleaned_data.get("DELETE"):
            continue
        values.append(
            {
                "tender_item_id": form.cleaned_data["tender_item"].pk,
                "line_number": form.cleaned_data["line_number"],
                "supplier_offer_id": form.cleaned_data[
                    "supplier_offer"
                ].pk,
                "allocated_quantity": form.cleaned_data[
                    "allocated_quantity"
                ],
            }
        )
    return values


def _result_queryset():
    return ProcurementResult.objects.select_related(
        "tender_revision__tender_request",
        "source_result",
        "created_by",
    ).prefetch_related(
        "items__allocations__supplier_offer__supplier",
        "items__allocations__supplier_offer__product",
    )


def _result_initial(result):
    return [
        {
            "tender_item": (
                allocation.procurement_result_item.tender_request_item
            ),
            "line_number": allocation.line_number,
            "supplier_offer": allocation.supplier_offer,
            "allocated_quantity": allocation.allocated_quantity,
        }
        for allocation in SupplierAllocation.objects.filter(
            procurement_result_item__procurement_result=result
        ).select_related(
            "procurement_result_item__tender_request_item",
            "supplier_offer",
        )
    ]


@login_required
def result_list(request):
    require_procurement_staff(request.user)
    results = _result_queryset()
    tender_id = request.GET.get("tender")
    if tender_id:
        results = results.filter(
            tender_revision__tender_request_id=tender_id
        )
    tender_ids = {
        result.tender_revision.tender_request_id for result in results
    }
    selections = {}
    selection_rows = ProcurementResultSelection.objects.filter(
        tender_request_id__in=tender_ids
    ).select_related("procurement_result").order_by(
        "tender_request_id", "-selection_number"
    )
    for selection in selection_rows:
        selections.setdefault(selection.tender_request_id, selection)
    rows = [
        {
            "result": result,
            "selected": (
                selections.get(result.tender_revision.tender_request_id)
                is not None
                and selections[
                    result.tender_revision.tender_request_id
                ].procurement_result_id
                == result.pk
            ),
        }
        for result in results
    ]
    return render(request, "sourcing/result_list.html", {"rows": rows})


@login_required
def result_detail(request, result_id):
    require_procurement_staff(request.user)
    result = get_object_or_404(_result_queryset(), pk=result_id)
    current_selection = ProcurementResultSelection.objects.filter(
        tender_request=result.tender_revision.tender_request
    ).first()
    return render(
        request,
        "sourcing/result_detail.html",
        {
            "result": result,
            "current_selection": current_selection,
        },
    )


@login_required
def result_create(request):
    require_procurement_staff(request.user)
    if request.method == "POST":
        selection_data = request.POST
    else:
        selection_data = request.GET.copy()
        if (
            "revision" in selection_data
            and "tender_revision" not in selection_data
        ):
            selection_data["tender_revision"] = selection_data["revision"]
    form = ManualResultForm(selection_data or None)
    form_valid = form.is_valid() if selection_data else False
    revision = (
        form.cleaned_data.get("tender_revision") if form_valid else None
    )
    formset = None
    if revision is not None:
        formset = ResultAllocationFormSet(
            request.POST or None,
            prefix="allocations",
            form_kwargs={"tender_revision": revision},
        )
    response_status = 200
    if (
        request.method == "POST"
        and form_valid
        and formset is not None
        and formset.is_valid()
    ):
        try:
            result = create_manual_result(
                actor=request.user,
                tender_revision_id=revision.pk,
                allocations=_allocation_values(formset),
                correlation_id=request.correlation_id,
            )
        except ValidationError as error:
            _add_result_error(form, formset, error)
        else:
            return redirect("sourcing:result-detail", result_id=result.pk)
    return render(
        request,
        "sourcing/result_form.html",
        {
            "form": form,
            "formset": formset,
            "title": "Buat Procurement Result manual",
            "is_update": False,
            "revision": revision,
        },
        status=response_status,
    )


@login_required
def result_update(request, result_id):
    require_procurement_staff(request.user)
    result = get_object_or_404(_result_queryset(), pk=result_id)
    if result.status != ResultStatus.DRAFT:
        return HttpResponse(
            "Hanya Procurement Result DRAFT yang dapat diubah.", status=409
        )
    initial = _result_initial(result)
    existing_offer_ids = {
        value["supplier_offer"].pk for value in initial
    }
    version_form = ExpectedVersionForm(
        request.POST or None,
        initial={"expected_version": result.version},
    )
    formset = ResultAllocationFormSet(
        request.POST or None,
        initial=initial,
        prefix="allocations",
        form_kwargs={
            "tender_revision": result.tender_revision,
            "existing_offer_ids": existing_offer_ids,
        },
    )
    response_status = 200
    if (
        request.method == "POST"
        and version_form.is_valid()
        and formset.is_valid()
    ):
        try:
            update_draft_result(
                actor=request.user,
                result_id=result.pk,
                expected_version=version_form.cleaned_data[
                    "expected_version"
                ],
                allocations=_allocation_values(formset),
                correlation_id=request.correlation_id,
            )
        except ValidationError as error:
            _add_result_error(version_form, formset, error)
            if isinstance(error, (ConcurrencyConflict, InvalidTransition)):
                response_status = 409
        else:
            return redirect("sourcing:result-detail", result_id=result.pk)
    return render(
        request,
        "sourcing/result_form.html",
        {
            "form": version_form,
            "formset": formset,
            "title": "Ubah Procurement Result",
            "result": result,
            "is_update": True,
        },
        status=response_status,
    )


@login_required
@require_POST
def result_validate(request, result_id):
    require_procurement_staff(request.user)
    form = ExpectedVersionForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Versi data tidak valid.", status=400)
    try:
        validate_result(
            actor=request.user,
            result_id=result_id,
            expected_version=form.cleaned_data["expected_version"],
            correlation_id=request.correlation_id,
        )
    except (ConcurrencyConflict, InvalidTransition) as error:
        return HttpResponse(error.messages[0], status=409)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(
            request, "Procurement Result berhasil divalidasi."
        )
    return redirect("sourcing:result-detail", result_id=result_id)


@login_required
@require_POST
def result_customize(request, result_id):
    require_procurement_staff(request.user)
    try:
        customized = customize_result(
            actor=request.user,
            source_result_id=result_id,
            correlation_id=request.correlation_id,
        )
    except InvalidTransition as error:
        return HttpResponse(error.messages[0], status=409)
    return redirect("sourcing:result-update", result_id=customized.pk)


@login_required
@require_POST
def result_select(request, result_id):
    require_procurement_staff(request.user)
    try:
        select_result(
            actor=request.user,
            result_id=result_id,
            correlation_id=request.correlation_id,
        )
    except InvalidTransition as error:
        return HttpResponse(error.messages[0], status=409)
    messages.success(request, "Procurement Result dipilih.")
    return redirect("sourcing:result-detail", result_id=result_id)


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
