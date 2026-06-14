from django import forms

from .models import DEFAULT_SELECTED_ITEMS, ITEM_CHOICES


class FilingSearchForm(forms.Form):
    YEAR_MODES = (
        ("fiscal", "Fiscal year"),
        ("filed", "Filed year"),
    )

    company = forms.CharField(
        label="Company or ticker",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "MSFT or Microsoft"}),
    )
    year = forms.IntegerField(label="Year", min_value=1994, max_value=2100)
    year_mode = forms.ChoiceField(
        label="Year type",
        choices=YEAR_MODES,
        widget=forms.RadioSelect,
        initial="fiscal",
    )
    item_codes = forms.MultipleChoiceField(
        label="SEC items to extract",
        choices=ITEM_CHOICES,
        initial=DEFAULT_SELECTED_ITEMS,
        widget=forms.CheckboxSelectMultiple,
        help_text="Choose one or more 10-K sections for extraction.",
    )


class CompanyChoiceForm(forms.Form):
    cik = forms.IntegerField(widget=forms.HiddenInput)
    name = forms.CharField(widget=forms.HiddenInput)
    ticker = forms.CharField(required=False, widget=forms.HiddenInput)
    exchange = forms.CharField(required=False, widget=forms.HiddenInput)
    year = forms.IntegerField(widget=forms.HiddenInput)
    year_mode = forms.CharField(widget=forms.HiddenInput)
    item_codes = forms.CharField(widget=forms.HiddenInput, required=False)


class FilingChoiceForm(forms.Form):
    accession_number = forms.CharField(widget=forms.HiddenInput)
