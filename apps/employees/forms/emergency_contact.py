from __future__ import annotations

from django import forms

from apps.employees.models import EmergencyContact


class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = EmergencyContact
        fields = [
            "name",
            "relationship",
            "mobile_number",
            "phone_number",
            "email",
            "address",
            "is_primary",
        ]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}
