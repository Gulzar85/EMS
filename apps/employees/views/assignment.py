"""Position- and manager-assignment CBVs. Each is a FormView calling one
`EmployeeAssignmentService`/`EmployeeManagerService` method — the service
owns ending the previous primary assignment and syncing
`Employee.current_position`/`current_manager` atomically (Phase 04 brief
§18-§26)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView

from apps.core.mixins import HtmxRedirectMixin
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.forms import (
    ManagerAssignmentForm,
    PositionAssignmentEndForm,
    PrimaryPositionAssignmentForm,
    SecondaryPositionAssignmentForm,
)
from apps.employees.models import EmployeePositionAssignment
from apps.employees.services import EmployeeAssignmentService, EmployeeManagerService
from apps.employees.views._shared import _get_employee_or_404


def _error_text(exc: Exception) -> str:
    """`EmployeeValidationError` (a plain domain exception) stringifies
    cleanly via `str()`; Django's `ValidationError` — raised by
    `full_clean()` deeper inside a service, e.g. an end date crossing an
    adjacent assignment's start date — needs `.messages` instead, or the
    user sees a raw `["..."]` list repr."""
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)
    return str(exc)


class _EmployeeScopedFormView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "employees.change_employee"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.employee = _get_employee_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["employee"] = self.employee
        return context

    def _redirect_to_detail(self):
        return self.redirect(
            reverse("employees:employee-detail", kwargs={"public_id": self.employee.public_id})
        )


class EmployeeAssignmentCreateView(_EmployeeScopedFormView):
    """Adds a secondary/acting/temporary assignment alongside the employee's
    current primary position."""

    form_class = SecondaryPositionAssignmentForm
    template_name = "employees/employee_assignment_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Add Assignment — {self.employee.display_name}"
        return context

    def form_valid(self, form):
        try:
            EmployeeAssignmentService.assign_position(
                employee=self.employee,
                position=form.cleaned_data["position"],
                assignment_type=form.cleaned_data["assignment_type"],
                is_primary=False,
                start_date=form.cleaned_data["start_date"],
                reason=form.cleaned_data["reason"],
                notes=form.cleaned_data["notes"],
                actor=self.request.user,
            )
        except (EmployeeValidationError, ValidationError) as exc:
            messages.error(self.request, _error_text(exc))
        else:
            messages.success(self.request, "Assignment added.")
        return self._redirect_to_detail()


class EmployeeAssignmentUpdateView(_EmployeeScopedFormView):
    """Changes the employee's PRIMARY position — ends the current primary
    assignment and starts a new one."""

    form_class = PrimaryPositionAssignmentForm
    template_name = "employees/employee_assignment_primary_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Change Position — {self.employee.display_name}"
        return context

    def form_valid(self, form):
        try:
            EmployeeAssignmentService.assign_position(
                employee=self.employee,
                position=form.cleaned_data["position"],
                assignment_type=EmployeePositionAssignment.AssignmentType.PRIMARY,
                is_primary=True,
                start_date=form.cleaned_data["start_date"],
                reason=form.cleaned_data["reason"],
                actor=self.request.user,
            )
        except (EmployeeValidationError, ValidationError) as exc:
            messages.error(self.request, _error_text(exc))
        else:
            messages.success(self.request, "Primary position updated.")
        return self._redirect_to_detail()


class EmployeeAssignmentEndView(_EmployeeScopedFormView):
    form_class = PositionAssignmentEndForm
    template_name = "employees/employee_assignment_confirm_end.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.assignment = get_object_or_404(
            EmployeePositionAssignment, pk=kwargs["assignment_id"], employee=self.employee
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["assignment"] = self.assignment
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        context["page_title"] = f"End Assignment — {self.employee.display_name}"
        return context

    def form_valid(self, form):
        try:
            EmployeeAssignmentService.end_assignment(
                assignment=self.assignment,
                end_date=form.cleaned_data["end_date"],
                reason=form.cleaned_data["reason"],
                actor=self.request.user,
            )
        except (EmployeeValidationError, ValidationError) as exc:
            messages.error(self.request, _error_text(exc))
        else:
            messages.success(self.request, "Assignment ended.")
        return self._redirect_to_detail()


class EmployeeManagerAssignmentView(_EmployeeScopedFormView):
    """Changes the employee's manager — ends the current primary manager
    assignment (if any) and starts a new one."""

    form_class = ManagerAssignmentForm
    template_name = "employees/employee_manager_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["employee"] = self.employee
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Change Manager — {self.employee.display_name}"
        return context

    def form_valid(self, form):
        try:
            EmployeeManagerService.assign_manager(
                employee=self.employee,
                manager=form.cleaned_data["manager"],
                relationship_type=form.cleaned_data["relationship_type"],
                start_date=form.cleaned_data["start_date"],
                actor=self.request.user,
            )
        except (EmployeeValidationError, ValidationError) as exc:
            messages.error(self.request, _error_text(exc))
        else:
            messages.success(self.request, "Manager updated.")
        return self._redirect_to_detail()
