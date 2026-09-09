from __future__ import annotations

from django import forms

from apps.employees.models import EmployeeEmployment

_TERMINAL_STATUS_CHOICES = [
    (EmployeeEmployment.Status.RESIGNED, EmployeeEmployment.Status.RESIGNED.label),
    (EmployeeEmployment.Status.TERMINATED, EmployeeEmployment.Status.TERMINATED.label),
    (EmployeeEmployment.Status.RETIRED, EmployeeEmployment.Status.RETIRED.label),
]


class EmployeeActionForm(forms.Form):
    """A reason-only confirmation form, reused across activate/confirm/
    place-on-leave/return/suspend/reinstate — mirrors
    `apps.organization.forms.PositionActionForm`."""

    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class EmployeeDeactivateForm(forms.Form):
    status = forms.ChoiceField(choices=_TERMINAL_STATUS_CHOICES, label="Reason for leaving")
    effective_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
