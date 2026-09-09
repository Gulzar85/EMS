"""JobFamily / JobLevel / Job CRUD views. These three are global master
data (not scoped to the organizational hierarchy — see
apps.organization.selectors's "Job master data" section), and are simple
enough that no service layer exists for them (see the docstring at the
top of apps/organization/services.py on not wrapping .save() in a
service merely for the sake of it) — Create/UpdateView call form.save()
directly.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.organization import selectors
from apps.organization.forms import JobFamilyForm, JobForm, JobLevelForm
from apps.organization.models import JobFamily, JobLevel

# --- JobFamily ---------------------------------------------------------


class JobFamilyListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_jobfamily"
    template_name = "organization/job_family_list.html"
    partial_template_name = "organization/partials/job_family_table.html"
    context_object_name = "job_families"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_job_families_for_list(q=self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["page_title"] = "Job Families"
        return context


class JobFamilyDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_jobfamily"
    template_name = "organization/job_family_detail.html"
    context_object_name = "job_family"

    def get_queryset(self):
        return selectors.get_job_families_for_list()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["jobs"] = self.object.jobs.order_by("title")
        context["page_title"] = self.object.name
        return context


class JobFamilyCreateView(
    PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView
):
    permission_required = "organization.add_jobfamily"
    form_class = JobFamilyForm
    template_name = "organization/job_family_form.html"
    partial_template_name = "organization/partials/job_family_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Job Family"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Job family "{self.object.name}" created.')
        return self.redirect(
            reverse("organization:job-family-detail", kwargs={"public_id": self.object.public_id})
        )


class JobFamilyUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "organization.change_jobfamily"
    form_class = JobFamilyForm
    template_name = "organization/job_family_form.html"
    partial_template_name = "organization/partials/job_family_form.html"
    context_object_name = "job_family"

    def get_queryset(self):
        return selectors.get_job_families_for_list()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Job family "{self.object.name}" updated.')
        return self.redirect(
            reverse("organization:job-family-detail", kwargs={"public_id": self.object.public_id})
        )


class JobFamilyDeleteView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView
):
    permission_required = "organization.delete_jobfamily"
    template_name = "organization/job_family_confirm_delete.html"
    success_url = reverse_lazy("organization:job-family-list")
    context_object_name = "job_family"

    def get_queryset(self):
        return selectors.get_job_families_for_list()

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
                "This job family cannot be deleted while jobs still reference it. "
                "Deactivate it instead.",
            )
            return self.redirect(
                reverse(
                    "organization:job-family-detail", kwargs={"public_id": self.object.public_id}
                )
            )
        messages.success(self.request, f'Job family "{self.object.name}" deleted.')
        return self.redirect(str(self.success_url))


# --- JobLevel ------------------------------------------------------------


class JobLevelListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_joblevel"
    template_name = "organization/job_level_list.html"
    partial_template_name = "organization/partials/job_level_table.html"
    context_object_name = "job_levels"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_job_levels_for_list(q=self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["page_title"] = "Job Levels"
        return context


class JobLevelDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_joblevel"
    template_name = "organization/job_level_detail.html"
    context_object_name = "job_level"

    def get_queryset(self):
        return selectors.get_job_levels_for_list()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["jobs"] = self.object.jobs.order_by("title")
        context["page_title"] = self.object.name
        return context


class JobLevelCreateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView):
    permission_required = "organization.add_joblevel"
    form_class = JobLevelForm
    template_name = "organization/job_level_form.html"
    partial_template_name = "organization/partials/job_level_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Job Level"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Job level "{self.object.name}" created.')
        return self.redirect(
            reverse("organization:job-level-detail", kwargs={"public_id": self.object.public_id})
        )


class JobLevelUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "organization.change_joblevel"
    form_class = JobLevelForm
    template_name = "organization/job_level_form.html"
    partial_template_name = "organization/partials/job_level_form.html"
    context_object_name = "job_level"

    def get_queryset(self):
        return selectors.get_job_levels_for_list()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Job level "{self.object.name}" updated.')
        return self.redirect(
            reverse("organization:job-level-detail", kwargs={"public_id": self.object.public_id})
        )


class JobLevelDeleteView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView
):
    permission_required = "organization.delete_joblevel"
    template_name = "organization/job_level_confirm_delete.html"
    success_url = reverse_lazy("organization:job-level-list")
    context_object_name = "job_level"

    def get_queryset(self):
        return selectors.get_job_levels_for_list()

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
                "This job level cannot be deleted while jobs still reference it. "
                "Deactivate it instead.",
            )
            return self.redirect(
                reverse(
                    "organization:job-level-detail", kwargs={"public_id": self.object.public_id}
                )
            )
        messages.success(self.request, f'Job level "{self.object.name}" deleted.')
        return self.redirect(str(self.success_url))


# --- Job -------------------------------------------------------------------


class JobListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "organization.view_job"
    template_name = "organization/job_list.html"
    partial_template_name = "organization/partials/job_table.html"
    context_object_name = "jobs"
    paginate_by = 25

    def get_queryset(self):
        return selectors.get_jobs_for_list(
            q=self.request.GET.get("q", "").strip(),
            job_family=self.request.GET.get("job_family") or None,
            job_level=self.request.GET.get("job_level") or None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["selected_job_family"] = self.request.GET.get("job_family", "")
        context["selected_job_level"] = self.request.GET.get("job_level", "")
        context["job_family_options"] = JobFamily.objects.filter(is_active=True).order_by("name")
        context["job_level_options"] = JobLevel.objects.filter(is_active=True).order_by("rank")
        context["page_title"] = "Jobs"
        return context


class JobDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "organization.view_job"
    template_name = "organization/job_detail.html"
    context_object_name = "job"

    def get_queryset(self):
        return selectors.get_jobs_for_list()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        positions = self.object.positions.order_by("code")
        context["positions"] = positions[:20]
        context["position_count"] = positions.count()
        context["page_title"] = self.object.title
        return context


class JobCreateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView):
    permission_required = "organization.add_job"
    form_class = JobForm
    template_name = "organization/job_form.html"
    partial_template_name = "organization/partials/job_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New Job"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Job "{self.object.title}" created.')
        return self.redirect(
            reverse("organization:job-detail", kwargs={"public_id": self.object.public_id})
        )


class JobUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "organization.change_job"
    form_class = JobForm
    template_name = "organization/job_form.html"
    partial_template_name = "organization/partials/job_form.html"
    context_object_name = "job"

    def get_queryset(self):
        return selectors.get_jobs_for_list()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.title}"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Job "{self.object.title}" updated.')
        return self.redirect(
            reverse("organization:job-detail", kwargs={"public_id": self.object.public_id})
        )


class JobDeleteView(PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView):
    permission_required = "organization.delete_job"
    template_name = "organization/job_confirm_delete.html"
    success_url = reverse_lazy("organization:job-list")
    context_object_name = "job"

    def get_queryset(self):
        return selectors.get_jobs_for_list()

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
                "This job cannot be deleted while positions still reference it. "
                "Deactivate it instead.",
            )
            return self.redirect(
                reverse("organization:job-detail", kwargs={"public_id": self.object.public_id})
            )
        messages.success(self.request, f'Job "{self.object.title}" deleted.')
        return self.redirect(str(self.success_url))
