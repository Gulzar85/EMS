from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.organization import selectors, services
from apps.organization.forms import OrganizationUnitForm


class OrganizationUnitListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_organizationunit"
    template_name = "organization/organization_unit_list.html"
    partial_template_name = "organization/partials/organization_unit_table.html"
    context_object_name = "units"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_organization_units_for_list(
            self.request.user, q=self.request.GET.get("q", "").strip()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["page_title"] = "Organization Units"
        return context


class OrganizationUnitDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_organizationunit"
    template_name = "organization/organization_unit_detail.html"
    context_object_name = "unit"

    def get_queryset(self):
        return selectors.get_organization_units_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        unit = self.object
        context["children"] = selectors.get_child_units(unit.id, self.request.user)
        context["locations"] = unit.locations.order_by("name")
        context["page_title"] = unit.name
        return context


class OrganizationUnitCreateView(
    PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView
):
    permission_required = "organization.add_organizationunit"
    form_class = OrganizationUnitForm
    template_name = "organization/organization_unit_form.html"
    partial_template_name = "organization/partials/organization_unit_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Organization Unit"
        return context

    def form_valid(self, form):
        unit = services.create_organization_unit(
            company=form.cleaned_data["company"],
            parent=form.cleaned_data["parent"],
            name=form.cleaned_data["name"],
            code=form.cleaned_data["code"],
            unit_type=form.cleaned_data["unit_type"],
            description=form.cleaned_data["description"],
            actor=self.request.user,
        )
        messages.success(self.request, f'Organization unit "{unit.name}" created.')
        return self.redirect(
            reverse("organization:unit-detail", kwargs={"public_id": unit.public_id})
        )


class OrganizationUnitUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "organization.change_organizationunit"
    form_class = OrganizationUnitForm
    template_name = "organization/organization_unit_form.html"
    partial_template_name = "organization/partials/organization_unit_form.html"
    context_object_name = "unit"

    def get_queryset(self):
        return selectors.get_organization_units_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        return context

    def form_valid(self, form):
        unit = services.update_organization_unit(
            unit=self.object, actor=self.request.user, **form.cleaned_data
        )
        messages.success(self.request, f'Organization unit "{unit.name}" updated.')
        return self.redirect(
            reverse("organization:unit-detail", kwargs={"public_id": unit.public_id})
        )


class OrganizationUnitDeleteView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView
):
    permission_required = "organization.delete_organizationunit"
    template_name = "organization/organization_unit_confirm_delete.html"
    success_url = reverse_lazy("organization:unit-list")
    context_object_name = "unit"

    def get_queryset(self):
        return selectors.get_organization_units_for_list(self.request.user)

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
                "This unit cannot be deleted while it still has child units, locations, "
                "or positions. Deactivate it instead.",
            )
            return self.redirect(
                reverse("organization:unit-detail", kwargs={"public_id": self.object.public_id})
            )
        messages.success(self.request, f'Organization unit "{self.object.name}" deleted.')
        return self.redirect(str(self.success_url))
