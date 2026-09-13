from django import forms
from django.forms import BaseFormSet, formset_factory

from apps.catalog.models import Product


class TenderDetailsForm(forms.Form):
    internal_code = forms.CharField(max_length=50, label="Kode internal")
    tender_reference_number = forms.CharField(
        max_length=100,
        required=False,
        label="Nomor referensi tender",
    )
    institution_name = forms.CharField(
        max_length=255, label="Nama instansi"
    )
    institution_address = forms.CharField(
        required=False,
        label="Alamat instansi",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    title = forms.CharField(max_length=255, label="Judul tender")
    description = forms.CharField(
        required=False,
        label="Deskripsi",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    total_hps = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=0.01,
        required=False,
        label="Total HPS",
    )


class TenderRevisionForm(TenderDetailsForm):
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    revision_reason = forms.CharField(
        label="Alasan revisi",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["internal_code"].disabled = True


class TenderItemForm(forms.Form):
    line_number = forms.IntegerField(min_value=1, label="Nomor baris")
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(), label="Produk"
    )
    requested_quantity = forms.DecimalField(
        max_digits=18,
        decimal_places=3,
        min_value=0.001,
        label="Jumlah dibutuhkan",
    )
    unit = forms.CharField(max_length=32, label="Satuan")
    specification = forms.CharField(
        required=False,
        label="Spesifikasi",
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    description = forms.CharField(
        required=False,
        label="Keterangan",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        )


class TenderItemBaseFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        lines = set()
        item_count = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            item_count += 1
            line = form.cleaned_data["line_number"]
            if line in lines:
                raise forms.ValidationError("Nomor baris item harus unik.")
            lines.add(line)
        if item_count == 0:
            raise forms.ValidationError(
                "Tender harus memiliki minimal satu item."
            )


TenderItemFormSet = formset_factory(
    TenderItemForm,
    formset=TenderItemBaseFormSet,
    extra=1,
    can_delete=True,
)
