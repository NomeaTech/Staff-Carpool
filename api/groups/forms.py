from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Group


class GroupForm(forms.ModelForm):
    """Making a group, and its admins editing it."""

    class Meta:
        model = Group
        fields = ("name", "description")

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise forms.ValidationError(_("Enter a name for the group."))
        taken = Group.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError(_("There is already a group called %(name)s. Choose another name.") % {"name": name})
        return name

    def clean_description(self):
        return self.cleaned_data["description"].strip()
