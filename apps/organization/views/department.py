from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.organization import selectors, services
from apps.organization.forms import DepartmentForm


class DepartmentListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_department"
    template_name = "organization/department_list.html"
    partial_template_name = "organization/partials/department_table.html"
    context_object_name = "departments"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_departments_for_list(
            self.request.user, q=self.request.GET.get("q", "").strip()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["page_title"] = "Departments"
        return context


class DepartmentDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_department"
    template_name = "organization/department_detail.html"
    context_object_name = "department"

    def get_queryset(self):
        return selectors.get_departments_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object
        context["children"] = department.children.all()
        context["positions"] = selectors.get_department_positions(department)
        context["page_title"] = department.name
        return context


class DepartmentCreateView(
    PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView
):
    permission_required = "organization.add_department"
    form_class = DepartmentForm
    template_name = "organization/department_form.html"
    partial_template_name = "organization/partials/department_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Department"
        return context

    def form_valid(self, form):
        department = services.create_department(
            organization_unit=form.cleaned_data["organization_unit"],
            location=form.cleaned_data["location"],
            parent=form.cleaned_data["parent"],
            code=form.cleaned_data["code"],
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            actor=self.request.user,
        )
        messages.success(self.request, f'Department "{department.name}" created.')
        return self.redirect(
            reverse("organization:department-detail", kwargs={"public_id": department.public_id})
        )


class DepartmentUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "organization.change_department"
    form_class = DepartmentForm
    template_name = "organization/department_form.html"
    partial_template_name = "organization/partials/department_form.html"
    context_object_name = "department"

    def get_queryset(self):
        return selectors.get_departments_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        return context

    def form_valid(self, form):
        department = services.update_department(
            department=self.object, actor=self.request.user, **form.cleaned_data
        )
        messages.success(self.request, f'Department "{department.name}" updated.')
        return self.redirect(
            reverse("organization:department-detail", kwargs={"public_id": department.public_id})
        )


class DepartmentDeleteView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView
):
    permission_required = "organization.delete_department"
    template_name = "organization/department_confirm_delete.html"
    success_url = reverse_lazy("organization:department-list")
    context_object_name = "department"

    def get_queryset(self):
        return selectors.get_departments_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete {self.object.name}"
        return context

    def form_valid(self, form):
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "This department cannot be deleted while it still has sub-departments "
                "or positions. Deactivate it instead.",
            )
            return self.redirect(
                reverse(
                    "organization:department-detail", kwargs={"public_id": self.object.public_id}
                )
            )
        messages.success(self.request, f'Department "{self.object.name}" deleted.')
        return self.redirect(str(self.success_url))
