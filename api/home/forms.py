from django import forms

class SearchForm(forms.Form):
    start = forms.CharField(required=False)
    destination = forms.CharField(required=False)
    date = forms.CharField(required=False)

    offer = forms.BooleanField(required=False)
    request = forms.BooleanField(required=False)
    other = forms.BooleanField(required=False)