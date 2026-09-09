"""Employee lifecycle-transition CBVs — one thin FormView per transition,
mirroring apps/organization/views/position.py's Activate/Deactivate/
Freeze/Unfreeze pattern exactly: `setup()` fetches the target, `form_valid()`
calls one `EmployeeLifecycleService` method inside try/except."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.views.generic import FormView

from apps.core.mixins import HtmxRedirectMixin
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.forms import EmployeeActionForm, EmployeeDeactivateForm
from apps.employees.services import EmployeeLifecycleService
from apps.employees.views._shared import _get_employee_or_404


def _error_text(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)
    return str(exc)


class _EmployeeTransitionView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    """Shared plumbing for the six reason-only transitions. Subclasses set
    `service_method_name`, `template_name`, `action_label` (imperative, for
    the page title — "Suspend"), and `verb` (past tense, for the success
    message — "suspended")."""

    permission_required = "employees.change_employee"
    form_class = EmployeeActionForm
    service_method_name: str = ""
    action_label: str = ""
    verb: str = ""

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.employee = _get_employee_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["employee"] = self.employee
        context["page_title"] = f"{self.action_label} {self.employee.display_name}"
        return context

    def form_valid(self, form):
        service_method = getattr(EmployeeLifecycleService, self.service_method_name)
        try:
            service_method(
                employee=self.employee, actor=self.request.user, reason=form.cleaned_data["reason"]
            )
        except (EmployeeValidationError, ValidationError) as exc:
            messages.error(self.request, _error_text(exc))
        else:
            messages.success(self.request, f'Employee "{self.employee.display_name}" {self.verb}.')
        return self.redirect(
            reverse("employees:employee-detail", kwargs={"public_id": self.employee.public_id})
        )


class EmployeeActivateView(_EmployeeTransitionView):
    template_name = "employees/employee_confirm_activate.html"
    service_method_name = "activate"
    action_label = "Activate"
    verb = "activated"


class EmployeeConfirmView(_EmployeeTransitionView):
    template_name = "employees/employee_confirm_confirm.html"
    service_method_name = "confirm"
    action_label = "Confirm"
    verb = "confirmed"


class EmployeePlaceOnLeaveView(_EmployeeTransitionView):
    template_name = "employees/employee_confirm_place_on_leave.html"
    service_method_name = "place_on_leave"
    action_label = "Place on Leave"
    verb = "placed on leave"


class EmployeeReturnFromLeaveView(_EmployeeTransitionView):
    template_name = "employees/employee_confirm_return_from_leave.html"
    service_method_name = "return_from_leave"
    action_label = "Return from Leave"
    verb = "returned from leave"


class EmployeeSuspendView(_EmployeeTransitionView):
    template_name = "employees/employee_confirm_suspend.html"
    service_method_name = "suspend"
    action_label = "Suspend"
    verb = "suspended"


class EmployeeReinstateView(_EmployeeTransitionView):
    template_name = "employees/employee_confirm_reinstate.html"
    service_method_name = "reinstate"
    action_label = "Reinstate"
    verb = "reinstated"


class EmployeeDeactivateView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    """The one transition with extra fields (status/effective_date), so it
    doesn't fit the shared `_EmployeeTransitionView` shape."""

    permission_required = "employees.change_employee"
    form_class = EmployeeDeactivateForm
    template_name = "employees/employee_confirm_deactivate.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.employee = _get_employee_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["employee"] = self.employee
        context["page_title"] = f"Deactivate {self.employee.display_name}"
        return context

    def form_valid(self, form):
        try:
            EmployeeLifecycleService.deactivate(
                employee=self.employee,
                status=form.cleaned_data["status"],
                reason=form.cleaned_data["reason"],
                effective_date=form.cleaned_data["effective_date"],
                actor=self.request.user,
            )
        except (EmployeeValidationError, ValidationError) as exc:
            messages.error(self.request, _error_text(exc))
        else:
            messages.success(self.request, f'Employee "{self.employee.display_name}" deactivated.')
        return self.redirect(
            reverse("employees:employee-detail", kwargs={"public_id": self.employee.public_id})
        )
