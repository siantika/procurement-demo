from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.policies import require_admin
from apps.core.exceptions import ConcurrencyConflict
from apps.core.forms import ExpectedVersionForm

from .forms import ProductForm, SupplierForm
from .models import Product, Supplier
from .services import (
    create_product,
    create_supplier,
    deactivate_product,
    deactivate_supplier,
    update_product,
    update_supplier,
)


def _correlation_id(request):
    return request.correlation_id


def _service_error(form, error):
    if hasattr(error, "message_dict"):
        for field, messages in error.message_dict.items():
            target = field if field in form.fields else None
            for message in messages:
                form.add_error(target, message)
    else:
        form.add_error(None, error.messages[0])


@login_required
def product_list(request):
    require_admin(request.user)
    return render(
        request,
        "catalog/product_list.html",
        {"products": Product.objects.select_related("created_by")},
    )


@login_required
def product_detail(request, product_id):
    require_admin(request.user)
    product = get_object_or_404(
        Product.objects.select_related("created_by"), pk=product_id
    )
    return render(
        request,
        "catalog/product_detail.html",
        {"product": product},
    )


@login_required
def product_create(request):
    require_admin(request.user)
    form = ProductForm(request.POST or None)
    response_status = 200
    if request.method == "POST" and form.is_valid():
        values = {
            key: form.cleaned_data[key] for key in ProductForm.Meta.fields
        }
        try:
            create_product(
                actor=request.user,
                correlation_id=_correlation_id(request),
                **values,
            )
        except ValidationError as error:
            _service_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("catalog:product-list")
    return render(
        request,
        "catalog/entity_form.html",
        {"form": form, "title": "Tambah produk", "section": "Produk"},
        status=response_status,
    )


@login_required
def product_update(request, product_id):
    require_admin(request.user)
    product = get_object_or_404(Product, pk=product_id)
    form = ProductForm(request.POST or None, instance=product)
    response_status = 200
    if not request.POST:
        form.fields["expected_version"].initial = product.version
    if request.method == "POST" and form.is_valid():
        values = {
            key: form.cleaned_data[key] for key in ProductForm.Meta.fields
        }
        try:
            update_product(
                actor=request.user,
                product_id=product.pk,
                expected_version=form.cleaned_data["expected_version"],
                correlation_id=_correlation_id(request),
                **values,
            )
        except ValidationError as error:
            _service_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("catalog:product-list")
    return render(
        request,
        "catalog/entity_form.html",
        {"form": form, "title": "Ubah produk", "section": "Produk"},
        status=response_status,
    )


@login_required
@require_POST
def product_deactivate(request, product_id):
    require_admin(request.user)
    form = ExpectedVersionForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Versi data tidak valid.", status=400)
    try:
        deactivate_product(
            actor=request.user,
            product_id=product_id,
            expected_version=form.cleaned_data["expected_version"],
            correlation_id=_correlation_id(request),
        )
    except Product.DoesNotExist:
        return HttpResponse("Produk tidak ditemukan.", status=404)
    except ValidationError as error:
        return HttpResponse(error.messages[0], status=409)
    return redirect("catalog:product-list")


@login_required
def supplier_list(request):
    require_admin(request.user)
    return render(
        request,
        "catalog/supplier_list.html",
        {"suppliers": Supplier.objects.select_related("created_by")},
    )


@login_required
def supplier_detail(request, supplier_id):
    require_admin(request.user)
    supplier = get_object_or_404(
        Supplier.objects.select_related("created_by"), pk=supplier_id
    )
    return render(
        request,
        "catalog/supplier_detail.html",
        {"supplier": supplier},
    )


@login_required
def supplier_create(request):
    require_admin(request.user)
    form = SupplierForm(request.POST or None)
    response_status = 200
    if request.method == "POST" and form.is_valid():
        values = {
            key: form.cleaned_data[key] for key in SupplierForm.Meta.fields
        }
        try:
            create_supplier(
                actor=request.user,
                correlation_id=_correlation_id(request),
                **values,
            )
        except ValidationError as error:
            _service_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("catalog:supplier-list")
    return render(
        request,
        "catalog/entity_form.html",
        {"form": form, "title": "Tambah supplier", "section": "Supplier"},
        status=response_status,
    )


@login_required
def supplier_update(request, supplier_id):
    require_admin(request.user)
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    form = SupplierForm(request.POST or None, instance=supplier)
    response_status = 200
    if not request.POST:
        form.fields["expected_version"].initial = supplier.version
    if request.method == "POST" and form.is_valid():
        values = {
            key: form.cleaned_data[key] for key in SupplierForm.Meta.fields
        }
        try:
            update_supplier(
                actor=request.user,
                supplier_id=supplier.pk,
                expected_version=form.cleaned_data["expected_version"],
                correlation_id=_correlation_id(request),
                **values,
            )
        except ValidationError as error:
            _service_error(form, error)
            if isinstance(error, ConcurrencyConflict):
                response_status = 409
        else:
            return redirect("catalog:supplier-list")
    return render(
        request,
        "catalog/entity_form.html",
        {"form": form, "title": "Ubah supplier", "section": "Supplier"},
        status=response_status,
    )


@login_required
@require_POST
def supplier_deactivate(request, supplier_id):
    require_admin(request.user)
    form = ExpectedVersionForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Versi data tidak valid.", status=400)
    try:
        deactivate_supplier(
            actor=request.user,
            supplier_id=supplier_id,
            expected_version=form.cleaned_data["expected_version"],
            correlation_id=_correlation_id(request),
        )
    except Supplier.DoesNotExist:
        return HttpResponse("Supplier tidak ditemukan.", status=404)
    except ValidationError as error:
        return HttpResponse(error.messages[0], status=409)
    return redirect("catalog:supplier-list")
