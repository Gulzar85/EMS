from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.organization import selectors
from apps.organization.forms import LocationForm


class LocationListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_location"
    template_name = "organization/location_list.html"
    partial_template_name = "organization/partials/location_table.html"
    context_object_name = "locations"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_locations_for_list(
            self.request.user, q=self.request.GET.get("q", "").strip()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["page_title"] = "Locations"
        return context


class LocationDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_location"
    template_name = "organization/location_detail.html"
    context_object_name = "location"

    def get_queryset(self):
        return selectors.get_locations_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.object
        context["restaurant"] = getattr(location, "restaurant", None)
        context["departments"] = location.departments.order_by("name")
        context["page_title"] = location.name
        return context


class LocationCreateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView):
    permission_required = "organization.add_location"
    form_class = LocationForm
    template_name = "organization/location_form.html"
    partial_template_name = "organization/partials/location_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Location"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Location "{self.object.name}" created.')
        return self.redirect(
            reverse("organization:location-detail", kwargs={"public_id": self.object.public_id})
        )


class LocationUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "organization.change_location"
    form_class = LocationForm
    template_name = "organization/location_form.html"
    partial_template_name = "organization/partials/location_form.html"
    context_object_name = "location"

    def get_queryset(self):
        return selectors.get_locations_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Location "{self.object.name}" updated.')
        return self.redirect(
            reverse("organization:location-detail", kwargs={"public_id": self.object.public_id})
        )


class LocationDeleteView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView
):
    permission_required = "organization.delete_location"
    template_name = "organization/location_confirm_delete.html"
    success_url = reverse_lazy("organization:location-list")
    context_object_name = "location"

    def get_queryset(self):
        return selectors.get_locations_for_list(self.request.user)

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
                "This location cannot be deleted while it still has departments or positions "
                "referencing it. Deactivate it instead.",
            )
            return self.redirect(
                reverse("organization:location-detail", kwargs={"public_id": self.object.public_id})
            )
        messages.success(self.request, f'Location "{self.object.name}" deleted.')
        return self.redirect(str(self.success_url))
