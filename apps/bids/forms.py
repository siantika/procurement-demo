from decimal import Decimal

from django import forms

from apps.core.forms import ExpectedVersionForm


class TargetMarginForm(ExpectedVersionForm):
    target_margin_percent = forms.DecimalField(
        label="Target margin (%)",
        min_value=Decimal("0.0000"),
        max_value=Decimal("99.9999"),
        max_digits=7,
        decimal_places=4,
        help_text="Gunakan nilai antara 0 dan kurang dari 100 persen.",
    )
