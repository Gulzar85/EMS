from __future__ import annotations

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import DetailView

from apps.audit.models import AuditLog
from apps.core.mixins import PublicIDLookupMixin
from apps.employees import selectors
from apps.employees.models import Employee
from apps.employees.permissions import restrict_employees_for_detail


class EmployeeHistoryView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    """Assignment + manager + lifecycle history in one place — built from
    existing `EmployeePositionAssignment`/`EmployeeManagerAssignment` rows
    and the audit log, not a duplicate timeline table (Phase 04 brief
    §75-§77)."""

    permission_required = "employees.view_employee"
    template_name = "employees/employee_history.html"
    context_object_name = "employee"

    def get_queryset(self):
        return restrict_employees_for_detail(Employee.objects.all(), self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        context["assignment_history"] = selectors.get_assignment_history(employee)
        context["manager_history"] = selectors.get_manager_history(employee)
        context["audit_events"] = AuditLog.objects.filter(
            entity_type="Employee", entity_id=str(employee.public_id)
        )[:50]
        context["page_title"] = f"History — {employee.display_name}"
        return context
