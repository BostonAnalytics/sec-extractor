from django import forms


class ChatForm(forms.Form):
    question = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Ask about this filing"}),
        label="Question",
    )
