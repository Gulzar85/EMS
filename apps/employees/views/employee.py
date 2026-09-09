"""Employee CRUD CBVs — mirrors apps/organization/views/restaurant.py's
FormView-based Create/Update pattern (EmployeeCreateForm/EmployeeProfileForm
are plain Forms spanning Employee + EmployeeContact, not ModelForms)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, DetailView, FormView, ListView

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.employees import selectors
from apps.employees.forms import EmployeeCreateForm, EmployeeProfileForm
from apps.employees.models import Employee, EmployeeEmployment
from apps.employees.permissions import restrict_employees_for_detail
from apps.employees.services import EmployeeService
from apps.employees.views._shared import _get_employee_or_404
from apps.organization.models import Department, Job, Position


class EmployeeListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "employees.view_employee"
    template_name = "employees/employee_list.html"
    partial_template_name = "employees/partials/employee_table.html"
    context_object_name = "employees"
    paginate_by = 25

    def get_queryset(self):
        request = self.request
        return selectors.get_employees_for_list(
            request.user,
            q=request.GET.get("q", "").strip(),
            status=request.GET.get("status", "").strip(),
            employment_type=request.GET.get("employment_type", "").strip(),
            department=request.GET.get("department") or None,
            position=request.GET.get("position") or None,
            manager=request.GET.get("manager") or None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        context["q"] = request.GET.get("q", "")
        context["status"] = request.GET.get("status", "")
        context["employment_type"] = request.GET.get("employment_type", "")
        context["department"] = request.GET.get("department", "")
        context["position"] = request.GET.get("position", "")
        context["status_choices"] = EmployeeEmployment.Status.choices
        context["employment_type_choices"] = Job.EmploymentCategory.choices
        context["department_choices"] = Department.objects.filter(is_active=True).order_by("name")
        context["position_choices"] = Position.objects.filter(
            status=Position.Status.ACTIVE
        ).order_by("code")
        context["page_title"] = "Employees"
        return context


class EmployeeDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "employees.view_employee"
    template_name = "employees/employee_detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        return restrict_employees_for_detail(Employee.objects.all(), self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        context["current_assignments"] = selectors.get_current_assignments(employee)
        context["assignment_history"] = selectors.get_assignment_history(employee)[:10]
        context["manager_history"] = selectors.get_manager_history(employee)[:10]
        context["subordinates"] = selectors.get_subordinates(employee, self.request.user)
        context["emergency_contacts"] = employee.emergency_contacts.all()
        context["page_title"] = employee.display_name
        return context


class EmployeeCreateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, FormView):
    permission_required = "employees.add_employee"
    form_class = EmployeeCreateForm
    template_name = "employees/employee_form.html"
    partial_template_name = "employees/partials/employee_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Employee"
        return context

    def form_valid(self, form):
        employee = EmployeeService.create_employee(actor=self.request.user, **form.cleaned_data)
        messages.success(
            self.request, f'Employee "{employee.display_name}" ({employee.employee_number}) created.'
        )
        return self.redirect(
            reverse("employees:employee-detail", kwargs={"public_id": employee.public_id})
        )


class EmployeeUpdateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, FormView):
    permission_required = "employees.change_employee"
    form_class = EmployeeProfileForm
    template_name = "employees/employee_form.html"
    partial_template_name = "employees/partials/employee_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.employee = _get_employee_or_404(request.user, kwargs["public_id"])

    def get_form(self, form_class=None):
        form_class = form_class or self.get_form_class()
        if self.request.method == "POST":
            return form_class(self.request.POST, self.request.FILES)
        return form_class.from_employee(self.employee)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["employee"] = self.employee
        context["page_title"] = f"Edit {self.employee.display_name}"
        return context

    def form_valid(self, form):
        fields = dict(form.cleaned_data)
        if not fields.get("profile_photo"):
            fields.pop("profile_photo", None)  # keep the existing photo unless a new one was uploaded
        employee = EmployeeService.update_employee(
            employee=self.employee, actor=self.request.user, **fields
        )
        messages.success(self.request, f'Employee "{employee.display_name}" updated.')
        return self.redirect(
            reverse("employees:employee-detail", kwargs={"public_id": employee.public_id})
        )


class EmployeeDeleteView(PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView):
    """Only DRAFT employees (never activated) may be deleted outright —
    everyone else has real history and must be deactivated instead (Phase
    04 brief §36). The queryset restriction makes this a 404, not a 403,
    for a non-draft target — consistent with every other scope-based 404
    in this project."""

    permission_required = "employees.delete_employee"
    template_name = "employees/employee_confirm_delete.html"
    success_url = reverse_lazy("employees:employee-list")
    context_object_name = "employee"

    def get_queryset(self):
        qs = restrict_employees_for_detail(Employee.objects.all(), self.request.user)
        return qs.filter(employment__status=EmployeeEmployment.Status.DRAFT)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete {self.object.display_name}"
        return context

    def form_valid(self, form):
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "This employee cannot be deleted while related records still reference them.",
            )
            return self.redirect(
                reverse("employees:employee-detail", kwargs={"public_id": self.object.public_id})
            )
        messages.success(self.request, f'Employee "{self.object.display_name}" deleted.')
        return self.redirect(str(self.success_url))
