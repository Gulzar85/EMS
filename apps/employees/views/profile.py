from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views.generic import DetailView

from apps.employees import selectors


class MyProfileView(LoginRequiredMixin, DetailView):
    """Every logged-in user sees their own employee record, regardless of
    organization scope (Phase 04 brief §47) — deliberately NOT permission-
    gated on `employees.view_employee` the way the general roster is: a
    restaurant crew member with no HR permission at all can still view
    their own profile."""

    template_name = "employees/my_profile.html"
    context_object_name = "employee"

    def get_object(self, queryset=None):
        employee = selectors.get_my_profile(self.request.user)
        if employee is None:
            raise Http404("No employee record is linked to your account.")
        return employee

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        context["current_assignments"] = selectors.get_current_assignments(employee)
        context["assignment_history"] = selectors.get_assignment_history(employee)[:10]
        context["emergency_contacts"] = employee.emergency_contacts.all()
        context["page_title"] = "My Profile"
        return context
