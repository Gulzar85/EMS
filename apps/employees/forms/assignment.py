"""Assignment forms are plain Forms, not ModelForms — creating/ending an
assignment is a service-orchestrated action (ending the previous primary,
syncing `Employee.current_position`/`current_manager`), not a single
model save (Phase 04 brief §18-§26, mirroring the RestaurantForm pattern
from Phase 03).
"""

from __future__ import annotations

from django import forms

from apps.employees.models import EmployeeManagerAssignment, EmployeePositionAssignment
from apps.organization.models import Position

_SECONDARY_ASSIGNMENT_TYPES = [
    choice
    for choice in EmployeePositionAssignment.AssignmentType.choices
    if choice[0] != EmployeePositionAssignment.AssignmentType.PRIMARY
]


class PrimaryPositionAssignmentForm(forms.Form):
    """Changes an employee's primary position — ends the current primary
    assignment (if any) and starts a new one, atomically, in the service."""

    position = forms.ModelChoiceField(
        queryset=Position.objects.filter(status=Position.Status.ACTIVE)
    )
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class SecondaryPositionAssignmentForm(forms.Form):
    """Adds an additional (non-primary) assignment alongside the employee's
    current primary position — e.g. acting, temporary, or additional
    responsibility (Phase 04 brief §21)."""

    position = forms.ModelChoiceField(
        queryset=Position.objects.filter(status=Position.Status.ACTIVE)
    )
    assignment_type = forms.ChoiceField(choices=_SECONDARY_ASSIGNMENT_TYPES)
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class PositionAssignmentEndForm(forms.Form):
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._assignment = assignment

    def clean_end_date(self):
        end_date = self.cleaned_data["end_date"]
        if self._assignment and end_date < self._assignment.start_date:
            raise forms.ValidationError("End date cannot be before the assignment's start date.")
        return end_date


class ManagerAssignmentForm(forms.Form):
    manager = forms.ModelChoiceField(queryset=None, label="New manager")
    relationship_type = forms.ChoiceField(choices=EmployeeManagerAssignment.RelationshipType.choices)
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.employees.models import Employee

        queryset = Employee.objects.select_related("employment").order_by("employee_number")
        if employee is not None:
            queryset = queryset.exclude(pk=employee.pk)
        self.fields["manager"].queryset = queryset
