from django import forms

from apps.core.domain.identifiers import normalize_business_code

from .models import Product, Supplier


class ProductForm(forms.ModelForm):
    expected_version = forms.IntegerField(
        widget=forms.HiddenInput, required=False
    )

    class Meta:
        model = Product
        fields = ("code", "name", "description", "default_unit")
        labels = {
            "code": "Kode produk",
            "name": "Nama produk",
            "description": "Deskripsi",
            "default_unit": "Satuan utama",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean_code(self):
        return normalize_business_code(self.cleaned_data.get("code", ""))


class SupplierForm(forms.ModelForm):
    expected_version = forms.IntegerField(
        widget=forms.HiddenInput, required=False
    )

    class Meta:
        model = Supplier
        fields = (
            "code",
            "name",
            "contact_name",
            "email",
            "phone",
            "address",
        )
        labels = {
            "code": "Kode supplier",
            "name": "Nama supplier",
            "contact_name": "Nama kontak",
            "email": "Email",
            "phone": "Telepon",
            "address": "Alamat",
        }
        widgets = {"address": forms.Textarea(attrs={"rows": 4})}

    def clean_code(self):
        return normalize_business_code(self.cleaned_data.get("code", ""))
