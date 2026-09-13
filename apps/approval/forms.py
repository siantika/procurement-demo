from django import forms

from apps.core.forms import ExpectedVersionForm


class RejectBidForm(ExpectedVersionForm):
    reason = forms.CharField(
        label="Alasan penolakan",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
