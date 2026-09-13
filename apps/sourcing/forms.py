from django import forms

from apps.catalog.models import Product, Supplier

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
