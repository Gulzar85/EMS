"""Position CRUD + lifecycle-workflow CBVs.

Standard CRUD mirrors apps/organization/views/organization_unit.py. The
five lifecycle-workflow views (Activate/Deactivate/Freeze/Unfreeze/
Duplicate) mirror apps/theme/views.py's ThemePublishView/ThemeRollbackView/
ThemeActivateView/ThemeDuplicateView pattern: a FormView with setup()
fetching the target object, get_context_data() adding it to context, and
form_valid() calling a service function inside try/except for the domain
exception.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.organization import selectors, services
from apps.organization.exceptions import OrganizationValidationError
from apps.organization.forms import PositionActionForm, PositionDuplicateForm, PositionForm
from apps.organization.models import Department, JobFamily, Position


def _get_position_or_404(user, public_id) -> Position:
    qs = selectors.get_positions_for_list(user)
    return get_object_or_404(qs, public_id=public_id)


class PositionListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_position"
    template_name = "organization/position_list.html"
    partial_template_name = "organization/partials/position_table.html"
    context_object_name = "positions"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_positions_for_list(
            self.request.user,
            q=self.request.GET.get("q", "").strip(),
            status=self.request.GET.get("status", "").strip(),
            job_family=self.request.GET.get("job_family") or None,
            department=self.request.GET.get("department") or None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["status"] = self.request.GET.get("status", "")
        context["job_family"] = self.request.GET.get("job_family", "")
        context["department"] = self.request.GET.get("department", "")
        context["status_choices"] = Position.Status.choices
        context["job_family_choices"] = JobFamily.objects.filter(is_active=True).order_by("name")
        context["department_choices"] = Department.objects.filter(is_active=True).order_by("name")
        context["page_title"] = "Positions"
        return context


class PositionDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_position"
    template_name = "organization/position_detail.html"
    context_object_name = "position"

    def get_queryset(self):
        return selectors.get_positions_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        position = self.object
        context["direct_reports"] = position.direct_reports.select_related("job").order_by("code")
        context["page_title"] = position.title
        return context


class PositionCreateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView):
    permission_required = "organization.add_position"
    form_class = PositionForm
    template_name = "organization/position_form.html"
    partial_template_name = "organization/partials/position_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Position"
        return context

    def form_valid(self, form):
        fields = dict(form.cleaned_data)
        job = fields.pop("job")
        organization_unit = fields.pop("organization_unit")
        department = fields.pop("department")
        reports_to = fields.pop("reports_to")
        code = fields.pop("code")
        title = fields.pop("title")
        position = services.create_position(
            job=job,
            organization_unit=organization_unit,
            department=department,
            reports_to=reports_to,
            code=code,
            title=title,
            actor=self.request.user,
            **fields,
        )
        messages.success(self.request, f'Position "{position.title}" created.')
        return self.redirect(
            reverse("organization:position-detail", kwargs={"public_id": position.public_id})
        )


class PositionUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "organization.change_position"
    form_class = PositionForm
    template_name = "organization/position_form.html"
    partial_template_name = "organization/partials/position_form.html"
    context_object_name = "position"

    def get_queryset(self):
        return selectors.get_positions_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.title}"
        return context

    def form_valid(self, form):
        position = services.update_position(
            position=self.object, actor=self.request.user, **form.cleaned_data
        )
        messages.success(self.request, f'Position "{position.title}" updated.')
        return self.redirect(
            reverse("organization:position-detail", kwargs={"public_id": position.public_id})
        )


class PositionDeleteView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView
):
    permission_required = "organization.delete_position"
    template_name = "organization/position_confirm_delete.html"
    success_url = reverse_lazy("organization:position-list")
    context_object_name = "position"

    def get_queryset(self):
        return selectors.get_positions_for_list(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete {self.object.title}"
        return context

    def form_valid(self, form):
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "This position cannot be deleted while other records still reference it. "
                "Deactivate it instead.",
            )
            return self.redirect(
                reverse("organization:position-detail", kwargs={"public_id": self.object.public_id})
            )
        messages.success(self.request, f'Position "{self.object.title}" deleted.')
        return self.redirect(str(self.success_url))


# --- Lifecycle workflow views -----------------------------------------------


class PositionActivateView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "organization.change_position"
    form_class = PositionActionForm
    template_name = "organization/position_confirm_activate.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.position = _get_position_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position"] = self.position
        context["page_title"] = f"Activate {self.position.title}"
        return context

    def form_valid(self, form):
        try:
            services.activate_position(
                position=self.position, actor=self.request.user, reason=form.cleaned_data["reason"]
            )
        except OrganizationValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, f'Position "{self.position.title}" activated.')
        return self.redirect(
            reverse("organization:position-detail", kwargs={"public_id": self.position.public_id})
        )


class PositionDeactivateView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "organization.change_position"
    form_class = PositionActionForm
    template_name = "organization/position_confirm_deactivate.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.position = _get_position_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position"] = self.position
        context["page_title"] = f"Deactivate {self.position.title}"
        return context

    def form_valid(self, form):
        try:
            services.deactivate_position(
                position=self.position, actor=self.request.user, reason=form.cleaned_data["reason"]
            )
        except OrganizationValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, f'Position "{self.position.title}" deactivated.')
        return self.redirect(
            reverse("organization:position-detail", kwargs={"public_id": self.position.public_id})
        )


class PositionFreezeView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "organization.change_position"
    form_class = PositionActionForm
    template_name = "organization/position_confirm_freeze.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.position = _get_position_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position"] = self.position
        context["page_title"] = f"Freeze {self.position.title}"
        return context

    def form_valid(self, form):
        try:
            services.freeze_position(
                position=self.position, actor=self.request.user, reason=form.cleaned_data["reason"]
            )
        except OrganizationValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, f'Position "{self.position.title}" frozen.')
        return self.redirect(
            reverse("organization:position-detail", kwargs={"public_id": self.position.public_id})
        )


class PositionUnfreezeView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "organization.change_position"
    form_class = PositionActionForm
    template_name = "organization/position_confirm_unfreeze.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.position = _get_position_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position"] = self.position
        context["page_title"] = f"Unfreeze {self.position.title}"
        return context

    def form_valid(self, form):
        try:
            services.unfreeze_position(
                position=self.position, actor=self.request.user, reason=form.cleaned_data["reason"]
            )
        except OrganizationValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, f'Position "{self.position.title}" unfrozen.')
        return self.redirect(
            reverse("organization:position-detail", kwargs={"public_id": self.position.public_id})
        )


class PositionDuplicateView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "organization.add_position"
    form_class = PositionDuplicateForm
    template_name = "organization/position_confirm_duplicate.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.position = _get_position_or_404(request.user, kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position"] = self.position
        context["page_title"] = f"Duplicate {self.position.title}"
        return context

    def form_valid(self, form):
        try:
            new_position = services.duplicate_position(
                position=self.position,
                new_code=form.cleaned_data["new_code"],
                new_title=form.cleaned_data["new_title"],
                actor=self.request.user,
            )
        except OrganizationValidationError as exc:
            messages.error(self.request, str(exc))
            return self.redirect(
                reverse(
                    "organization:position-detail", kwargs={"public_id": self.position.public_id}
                )
            )
        messages.success(self.request, f'Duplicated as "{new_position.title}".')
        return self.redirect(
            reverse("organization:position-detail", kwargs={"public_id": new_position.public_id})
        )
