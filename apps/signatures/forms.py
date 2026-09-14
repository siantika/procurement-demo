from django import forms

from apps.core.forms import ExpectedVersionForm


class SignBidForm(ExpectedVersionForm):
    confirmation = forms.BooleanField(
        label="Saya menyatakan telah memeriksa dan menyetujui Bid ini."
    )
    signature_image = forms.ImageField(
        label="Gambar tanda tangan (opsional)",
        required=False,
        help_text=(
            "PNG/JPEG, maksimum 1 MiB, resolusi 200×80 sampai "
            "2000×1000 piksel."
        ),
    )

    def clean_signature_image(self):
        image = self.cleaned_data.get("signature_image")
        if image is None:
            return None
        if image.size > 1_048_576:
            raise forms.ValidationError(
                "Ukuran gambar tanda tangan maksimum 1 MiB."
            )
        if image.content_type not in {"image/png", "image/jpeg"}:
            raise forms.ValidationError(
                "Gambar tanda tangan harus berupa PNG atau JPEG."
            )
        width, height = image.image.size
        if not (200 <= width <= 2000 and 80 <= height <= 1000):
            raise forms.ValidationError(
                "Resolusi gambar harus 200×80 sampai 2000×1000 piksel."
            )
        return image
