from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import FormView

from apps.core.mixins import HtmxRedirectMixin
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.forms import LinkUserForm, UnlinkUserConfirmForm
from apps.employees.services import EmployeeUserLinkService
from apps.employees.views._shared import _get_employee_or_404


class EmployeeUserLinkView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "employees.change_employee"
    form_class = LinkUserForm
    template_name = "employees/employee_user_link_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.employee = _get_employee_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["employee"] = self.employee
        context["page_title"] = f"Link User Account — {self.employee.display_name}"
        return context

    def form_valid(self, form):
        try:
            EmployeeUserLinkService.link_user(
                employee=self.employee, user=form.cleaned_data["user"], actor=self.request.user
            )
        except EmployeeValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, "User account linked.")
        return self.redirect(
            reverse("employees:employee-detail", kwargs={"public_id": self.employee.public_id})
        )


class EmployeeUserUnlinkView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "employees.change_employee"
    form_class = UnlinkUserConfirmForm
    template_name = "employees/employee_user_unlink_confirm.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.employee = _get_employee_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["employee"] = self.employee
        context["page_title"] = f"Unlink User Account — {self.employee.display_name}"
        return context

    def form_valid(self, form):
        try:
            EmployeeUserLinkService.unlink_user(employee=self.employee, actor=self.request.user)
        except EmployeeValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, "User account unlinked.")
        return self.redirect(
            reverse("employees:employee-detail", kwargs={"public_id": self.employee.public_id})
        )
