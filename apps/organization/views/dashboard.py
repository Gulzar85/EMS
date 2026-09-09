from __future__ import annotations

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from apps.organization import selectors
from apps.organization.models import OrganizationUnit


class OrganizationDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = "organization.view_organizationunit"
    template_name = "organization/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["metrics"] = selectors.get_organization_dashboard_metrics(self.request.user)
        context["root_units"] = selectors.get_root_units_for_user(self.request.user)
        context["page_title"] = "Organization"
        return context


class OrganizationUnitChildrenView(PermissionRequiredMixin, View):
    """HTMX-only: lazily loads one unit's children for the tree UI — the
    whole tree is never rendered/loaded at once (Phase 03 plan §67)."""

    permission_required = "organization.view_organizationunit"

    def get(self, request: HttpRequest, public_id, *args, **kwargs) -> HttpResponse:
        unit = get_object_or_404(OrganizationUnit, public_id=public_id)
        children = selectors.get_child_units(unit.id, request.user)
        return render(request, "organization/partials/_tree_children.html", {"children": children})
