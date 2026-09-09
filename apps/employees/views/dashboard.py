from __future__ import annotations

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import TemplateView

from apps.employees import selectors


class EmployeeDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = "employees.view_employee"
    template_name = "employees/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["metrics"] = selectors.get_employee_dashboard_metrics(self.request.user)
        context["page_title"] = "Employees"
        return context
