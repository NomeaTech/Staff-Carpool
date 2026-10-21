from django import forms

class SearchForm(forms.Form):
    start = forms.CharField(required=False)
    start_json = forms.JSONField(required=False)
    destination = forms.CharField(required=False)
    destination_json = forms.JSONField(required=False)
    date = forms.DateField(required=False)

    # The ways of travelling to show (test_app/transport.py): rides with any
    # of the ticked ones, or all rides when none is ticked
    offer = forms.BooleanField(required=False)
    request = forms.BooleanField(required=False)
    train = forms.BooleanField(required=False)
    bus = forms.BooleanField(required=False)
    taxi = forms.BooleanField(required=False)
    other = forms.BooleanField(required=False)