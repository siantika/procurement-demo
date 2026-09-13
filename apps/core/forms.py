from django import forms


class ExpectedVersionForm(forms.Form):
    """Payload minimal untuk operasi POST yang memakai optimistic lock."""

    expected_version = forms.IntegerField(
        min_value=1, widget=forms.HiddenInput
    )
