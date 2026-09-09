from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, DetailView, FormView, ListView

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.organization import selectors, services
from apps.organization.forms import RestaurantForm
from apps.organization.models import Position, Restaurant
from apps.organization.permissions import restrict_by_unit


class RestaurantListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_restaurant"
    template_name = "organization/restaurant_list.html"
    partial_template_name = "organization/partials/restaurant_table.html"
    context_object_name = "restaurants"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_restaurants_for_list(
            self.request.user,
            q=self.request.GET.get("q", "").strip(),
            status=self.request.GET.get("status", "").strip(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["status"] = self.request.GET.get("status", "")
        context["status_choices"] = Restaurant.OperationalStatus.choices
        context["page_title"] = "Restaurants"
        return context


class RestaurantDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_restaurant"
    template_name = "organization/restaurant_detail.html"
    context_object_name = "restaurant"

    def get_queryset(self):
        qs = Restaurant.objects.select_related("location", "location__organization_unit")
        return restrict_by_unit(
            qs, self.request.user, field_paths=["location__organization_unit_id"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.object
        location = restaurant.location
        departments = location.departments.order_by("name")
        context["departments"] = departments
        context["positions"] = (
            Position.objects.filter(department__location_id=location.id)
            .select_related("job", "department")
            .order_by("code")
        )
        context["page_title"] = f"Restaurant {restaurant.restaurant_number}"
        return context


class RestaurantCreateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, FormView):
    permission_required = "organization.add_restaurant"
    form_class = RestaurantForm
    template_name = "organization/restaurant_form.html"
    partial_template_name = "organization/partials/restaurant_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Restaurant"
        return context

    def form_valid(self, form):
        restaurant = services.create_restaurant(
            organization_unit=form.cleaned_data["organization_unit"],
            code=form.cleaned_data["code"],
            name=form.cleaned_data["name"],
            restaurant_number=form.cleaned_data["restaurant_number"],
            actor=self.request.user,
            restaurant_type=form.cleaned_data["restaurant_type"],
            operational_status=form.cleaned_data["operational_status"],
            address=form.cleaned_data["address"],
            city=form.cleaned_data["city"],
            district=form.cleaned_data["district"],
            province=form.cleaned_data["province"],
            postal_code=form.cleaned_data["postal_code"],
            phone=form.cleaned_data["phone"],
            email=form.cleaned_data["email"],
            opening_date=form.cleaned_data["opening_date"],
            closing_date=form.cleaned_data["closing_date"],
        )
        messages.success(self.request, f'Restaurant "{restaurant.restaurant_number}" created.')
        return self.redirect(
            reverse("organization:restaurant-detail", kwargs={"public_id": restaurant.public_id})
        )


class RestaurantUpdateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, FormView):
    permission_required = "organization.change_restaurant"
    form_class = RestaurantForm
    template_name = "organization/restaurant_form.html"
    partial_template_name = "organization/partials/restaurant_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        qs = Restaurant.objects.select_related("location")
        qs = restrict_by_unit(qs, request.user, field_paths=["location__organization_unit_id"])
        self.restaurant = get_object_or_404(qs, public_id=kwargs["public_id"])

    def get_form(self, form_class=None):
        form_class = form_class or self.get_form_class()
        if self.request.method == "POST":
            return form_class(self.request.POST)
        return form_class.from_restaurant(self.restaurant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["restaurant"] = self.restaurant
        context["page_title"] = f"Edit Restaurant {self.restaurant.restaurant_number}"
        return context

    def form_valid(self, form):
        fields = dict(form.cleaned_data)
        fields.pop("organization_unit", None)
        restaurant = services.update_restaurant(
            restaurant=self.restaurant, actor=self.request.user, **fields
        )
        messages.success(self.request, f'Restaurant "{restaurant.restaurant_number}" updated.')
        return self.redirect(
            reverse("organization:restaurant-detail", kwargs={"public_id": restaurant.public_id})
        )


class RestaurantDeleteView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView
):
    permission_required = "organization.delete_restaurant"
    template_name = "organization/restaurant_confirm_delete.html"
    success_url = reverse_lazy("organization:restaurant-list")
    context_object_name = "restaurant"

    def get_queryset(self):
        qs = Restaurant.objects.select_related("location")
        return restrict_by_unit(
            qs, self.request.user, field_paths=["location__organization_unit_id"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete Restaurant {self.object.restaurant_number}"
        return context

    def form_valid(self, form):
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "This restaurant cannot be deleted while related records still reference it.",
            )
            return self.redirect(
                reverse(
                    "organization:restaurant-detail", kwargs={"public_id": self.object.public_id}
                )
            )
        messages.success(self.request, f'Restaurant "{self.object.restaurant_number}" deleted.')
        return self.redirect(str(self.success_url))
