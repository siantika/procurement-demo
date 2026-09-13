from decimal import Decimal

from django import forms
from django.db.models import F, Q
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone

from apps.catalog.models import Product, Supplier
from apps.tender.models import TenderRequestItem, TenderRequestRevision

from .models import SupplierOffer


class SupplierOfferForm(forms.ModelForm):
    expected_version = forms.IntegerField(
        widget=forms.HiddenInput, required=False
    )

    class Meta:
        model = SupplierOffer
        fields = (
            "supplier",
            "product",
            "supplier_reference",
            "base_unit_price",
            "discount_percent",
            "available_quantity",
            "valid_from",
            "valid_until",
        )
        labels = {
            "supplier": "Supplier",
            "product": "Produk",
            "supplier_reference": "Referensi supplier",
            "base_unit_price": "Harga dasar per unit",
            "discount_percent": "Diskon (%)",
            "available_quantity": "Jumlah tersedia",
            "valid_from": "Berlaku mulai",
            "valid_until": "Berlaku sampai",
        }
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        lock_identity = kwargs.pop("lock_identity", False)
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(
            is_active=True
        )
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        )
        if lock_identity:
            self.fields["supplier"].disabled = True
            self.fields["product"].disabled = True
        self.fields["discount_percent"].help_text = (
            "Diskon 100% dapat dicatat, tetapi offer tidak eligible."
        )

    def clean(self):
        cleaned = super().clean()
        valid_from = cleaned.get("valid_from")
        valid_until = cleaned.get("valid_until")
        if valid_from and valid_until and valid_until < valid_from:
            self.add_error(
                "valid_until",
                "Tanggal akhir tidak boleh sebelum tanggal mulai.",
            )
        return cleaned


class TenderRevisionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, revision):
        return (
            f"{revision.tender_request.internal_code} — "
            f"R{revision.revision_number}: {revision.title}"
        )


class SupplierOfferChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, offer):
        availability = (
            f"maks. {offer.available_quantity}"
            if offer.available_quantity is not None
            else "tanpa batas"
        )
        return (
            f"{offer.supplier.code} — {offer.product.code} — "
            f"Rp{offer.net_purchase_price} ({availability})"
        )


class ManualResultForm(forms.Form):
    tender_revision = TenderRevisionChoiceField(
        queryset=TenderRequestRevision.objects.none(),
        label="Revision tender",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tender_revision"].queryset = (
            TenderRequestRevision.objects.filter(
                revision_number=F(
                    "tender_request__current_revision_number"
                )
            ).select_related("tender_request")
        )


class ResultAllocationForm(forms.Form):
    tender_item = forms.ModelChoiceField(
        queryset=TenderRequestItem.objects.none(),
        label="Item tender",
    )
    line_number = forms.IntegerField(
        min_value=1,
        label="Urutan allocation",
    )
    supplier_offer = SupplierOfferChoiceField(
        queryset=SupplierOffer.objects.none(),
        label="Supplier offer",
    )
    allocated_quantity = forms.DecimalField(
        max_digits=18,
        decimal_places=3,
        min_value=Decimal("0.001"),
        label="Jumlah allocation",
    )

    def __init__(self, *args, **kwargs):
        tender_revision = kwargs.pop("tender_revision", None)
        existing_offer_ids = kwargs.pop("existing_offer_ids", ())
        super().__init__(*args, **kwargs)
        if tender_revision is None:
            return
        item_queryset = tender_revision.items.select_related("product")
        product_ids = item_queryset.values_list("product_id", flat=True)
        today = timezone.localdate()
        eligible = Q(
            is_active=True,
            product__is_active=True,
            supplier__is_active=True,
            product_id__in=product_ids,
            currency="IDR",
            net_purchase_price__gt=0,
        ) & (Q(valid_from__isnull=True) | Q(valid_from__lte=today)) & (
            Q(valid_until__isnull=True) | Q(valid_until__gte=today)
        )
        self.fields["tender_item"].queryset = item_queryset
        self.fields["supplier_offer"].queryset = (
            SupplierOffer.objects.filter(
                eligible | Q(pk__in=existing_offer_ids)
            )
            .select_related("supplier", "product")
            .distinct()
        )


class ResultAllocationBaseFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen_lines = set()
        seen_offers = set()
        active_forms = 0
        for form in self.forms:
            values = form.cleaned_data
            if not values or values.get("DELETE"):
                continue
            active_forms += 1
            item_id = values["tender_item"].pk
            line_key = (item_id, values["line_number"])
            offer_key = (item_id, values["supplier_offer"].pk)
            if line_key in seen_lines:
                raise forms.ValidationError(
                    "Urutan allocation harus unik untuk setiap item."
                )
            if offer_key in seen_offers:
                raise forms.ValidationError(
                    "Supplier offer hanya boleh sekali untuk setiap item."
                )
            seen_lines.add(line_key)
            seen_offers.add(offer_key)
        if active_forms == 0:
            raise forms.ValidationError(
                "Tambahkan minimal satu supplier allocation."
            )


ResultAllocationFormSet = formset_factory(
    ResultAllocationForm,
    formset=ResultAllocationBaseFormSet,
    extra=3,
    can_delete=True,
)
