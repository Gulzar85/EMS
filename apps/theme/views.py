"""Theme CBVs.

Thin by design: every view's only job is HTTP plumbing (auth, form
wiring, template selection) — validation lives in forms, business rules
and persistence live in apps.theme.services. See
docs/architecture/application-architecture.md for the layering contract
this follows: CBV -> Form -> Service -> ORM.
"""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.mixins import HtmxRedirectMixin, HtmxTemplateMixin, PublicIDLookupMixin
from apps.theme import selectors, services
from apps.theme.exceptions import ThemeValidationError
from apps.theme.forms import (
    AppearanceForm,
    ThemeCreateForm,
    ThemeDuplicateForm,
    ThemePublishForm,
    ThemeRollbackForm,
    ThemeStudioForm,
    ThemeUpdateForm,
)
from apps.theme.models import Theme, UserThemePreference
from apps.theme.rendering import render_theme_css
from apps.theme.services import ThemeCacheService


def _get_theme_or_404(public_id) -> Theme:
    return get_object_or_404(Theme.objects.select_related("active_version"), public_id=public_id)


class ThemeListView(PermissionRequiredMixin, HtmxTemplateMixin, ListView):
    permission_required = "theme.view_theme"
    template_name = "theme/theme_list.html"
    partial_template_name = "theme/partials/theme_table.html"
    context_object_name = "themes"
    paginate_by = 12

    def get_queryset(self):
        return selectors.get_themes_for_list(q=self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["page_title"] = "Themes"
        return context


class ThemeDetailView(PermissionRequiredMixin, PublicIDLookupMixin, DetailView):
    permission_required = "theme.view_theme"
    template_name = "theme/theme_detail.html"
    context_object_name = "theme"

    def get_queryset(self):
        return Theme.objects.select_related("active_version")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        theme = self.object
        context["versions"] = selectors.get_theme_versions(theme)
        context["draft"] = selectors.get_draft_version(theme)
        context["publish_form"] = ThemePublishForm()
        published = selectors.get_published_versions(theme).exclude(pk=theme.active_version_id)
        if published.exists():
            context["rollback_form"] = ThemeRollbackForm(theme=theme)
        context["duplicate_form"] = ThemeDuplicateForm(initial={"new_name": f"{theme.name} copy"})
        context["page_title"] = theme.name
        return context


class ThemeCreateView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, CreateView):
    permission_required = "theme.add_theme"
    form_class = ThemeCreateForm
    template_name = "theme/theme_form.html"
    partial_template_name = "theme/partials/theme_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "New theme"
        return context

    def form_valid(self, form):
        theme = services.create_theme(
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            actor=self.request.user,
        )
        messages.success(self.request, f'Theme "{theme.name}" created.')
        return self.redirect(reverse("theme:studio", kwargs={"public_id": theme.public_id}))


class ThemeUpdateView(
    PermissionRequiredMixin, PublicIDLookupMixin, HtmxTemplateMixin, HtmxRedirectMixin, UpdateView
):
    permission_required = "theme.change_theme"
    form_class = ThemeUpdateForm
    template_name = "theme/theme_form.html"
    partial_template_name = "theme/partials/theme_form.html"

    def get_queryset(self):
        return Theme.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Theme "{self.object.name}" updated.')
        return self.redirect(reverse("theme:detail", kwargs={"public_id": self.object.public_id}))


class ThemeStudioView(PermissionRequiredMixin, HtmxTemplateMixin, HtmxRedirectMixin, FormView):
    """Not conventional CRUD — edits the theme's current DRAFT version via
    a service, not form.save() (Phase 02 plan CBV table)."""

    permission_required = "theme.change_theme"
    form_class = ThemeStudioForm
    template_name = "theme/theme_studio.html"
    partial_template_name = "theme/partials/theme_studio_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.theme = _get_theme_or_404(kwargs["public_id"])

    def get_initial_tokens(self) -> dict:
        version = selectors.get_draft_version(self.theme) or self.theme.active_version
        from apps.theme.validation import DEFAULT_THEME_TOKENS

        return version.tokens if version else DEFAULT_THEME_TOKENS

    def get_form(self, form_class=None):
        form_class = form_class or self.get_form_class()
        if self.request.method == "POST":
            return form_class(self.request.POST)
        return form_class.from_tokens(self.get_initial_tokens())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["theme"] = self.theme
        context["page_title"] = f"Theme Studio — {self.theme.name}"
        return context

    def form_valid(self, form):
        services.update_draft_tokens(
            theme=self.theme, tokens=form.cleaned_tokens, actor=self.request.user
        )
        messages.success(self.request, "Draft saved.")
        return self.redirect(reverse("theme:studio", kwargs={"public_id": self.theme.public_id}))


class ThemePreviewView(PermissionRequiredMixin, View):
    """GET-only: renders the theme's current saved draft as real CSS, for
    opening in a new tab. Never cached, never affects live/active state."""

    permission_required = "theme.view_theme"

    def get(self, request: HttpRequest, public_id) -> HttpResponse:
        theme = _get_theme_or_404(public_id)
        version = selectors.get_draft_version(theme) or theme.active_version
        css = render_theme_css(version.tokens) if version else ""
        return HttpResponse(css, content_type="text/css")


class ThemePublishView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "theme.publish_theme"
    form_class = ThemePublishForm
    template_name = "theme/theme_confirm_publish.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.theme = _get_theme_or_404(kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["theme"] = self.theme
        context["draft"] = selectors.get_draft_version(self.theme)
        context["page_title"] = f"Publish {self.theme.name}"
        return context

    def form_valid(self, form):
        draft = selectors.get_draft_version(self.theme)
        if draft is None:
            messages.error(self.request, "There is no draft to publish.")
            return self.redirect(
                reverse("theme:detail", kwargs={"public_id": self.theme.public_id})
            )
        try:
            services.publish_theme(
                theme=self.theme,
                version=draft,
                actor=self.request.user,
                reason=form.cleaned_data["reason"],
            )
        except ThemeValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, f'"{self.theme.name}" published and activated.')
        return self.redirect(reverse("theme:detail", kwargs={"public_id": self.theme.public_id}))


class ThemeRollbackView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "theme.rollback_theme"
    form_class = ThemeRollbackForm
    template_name = "theme/theme_confirm_rollback.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.theme = _get_theme_or_404(kwargs["public_id"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["theme"] = self.theme
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        target = self.request.GET.get("target_version")
        if target:
            initial["target_version"] = target
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["theme"] = self.theme
        context["page_title"] = f"Roll back {self.theme.name}"
        return context

    def form_valid(self, form):
        try:
            services.rollback_theme(
                theme=self.theme,
                target_version=form.cleaned_data["target_version"],
                actor=self.request.user,
                reason=form.cleaned_data["reason"],
            )
        except ThemeValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, f'"{self.theme.name}" rolled back.')
        return self.redirect(reverse("theme:detail", kwargs={"public_id": self.theme.public_id}))


class ThemeActivateView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "theme.activate_theme"
    form_class = forms.Form  # no fields — a bare confirm-and-POST action
    template_name = "theme/theme_confirm_activate.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.theme = _get_theme_or_404(kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["theme"] = self.theme
        context["page_title"] = f"Activate {self.theme.name}"
        return context

    def form_valid(self, form):
        try:
            services.activate_theme(theme=self.theme, actor=self.request.user)
        except ThemeValidationError as exc:
            messages.error(self.request, str(exc))
        else:
            messages.success(self.request, f'"{self.theme.name}" is now the active theme.')
        return self.redirect(reverse("theme:detail", kwargs={"public_id": self.theme.public_id}))


class ThemeDuplicateView(PermissionRequiredMixin, HtmxRedirectMixin, FormView):
    permission_required = "theme.add_theme"
    form_class = ThemeDuplicateForm
    template_name = "theme/theme_confirm_duplicate.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.theme = _get_theme_or_404(kwargs["public_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["theme"] = self.theme
        context["page_title"] = f"Duplicate {self.theme.name}"
        return context

    def form_valid(self, form):
        new_theme = services.duplicate_theme(
            theme=self.theme, actor=self.request.user, new_name=form.cleaned_data["new_name"]
        )
        messages.success(self.request, f'Duplicated as "{new_theme.name}".')
        return self.redirect(reverse("theme:studio", kwargs={"public_id": new_theme.public_id}))


class ThemeDeleteView(PermissionRequiredMixin, PublicIDLookupMixin, HtmxRedirectMixin, DeleteView):
    permission_required = "theme.delete_theme"
    template_name = "theme/theme_confirm_delete.html"
    success_url = reverse_lazy("theme:list")

    def get_queryset(self):
        return Theme.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete {self.object.name}"
        return context

    def form_valid(self, form):
        try:
            services.delete_theme(theme=self.object, actor=self.request.user)
        except ThemeValidationError as exc:
            messages.error(self.request, str(exc))
            return self.redirect(
                reverse("theme:detail", kwargs={"public_id": self.object.public_id})
            )
        messages.success(self.request, f'Theme "{self.object.name}" deleted.')
        return self.redirect(str(self.success_url))


class StyleguideView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Every required component in one place — living reference +
    the same partial reused as the Theme Studio's live-preview pane
    (Phase 02 plan judgment call #8)."""

    template_name = "theme/styleguide.html"

    def test_func(self) -> bool:
        return bool(self.request.user.is_staff)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Styleguide"
        return context


class AppearanceUpdateView(LoginRequiredMixin, View):
    """Any authenticated user may set their own appearance — no special
    permission, this only ever affects their own session.

    No redirect: Alpine already applied the change optimistically to
    `<html data-theme>` the instant the user clicked (see
    static/src/js/components/appearance.js) — this call only persists it
    for the *next* server-rendered page load. A plain 204 keeps that
    round-trip from being visible at all.
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        form = AppearanceForm(request.POST)
        if not form.is_valid():
            return HttpResponse(status=400)
        UserThemePreference.objects.update_or_create(
            user=request.user, defaults={"appearance": form.cleaned_data["appearance"]}
        )
        return HttpResponse(status=204)


class ThemeCSSView(View):
    """Public, unauthenticated, cached — serves only presentational data
    (colors/fonts/radii), nothing sensitive. See docs/frontend/theme-system.md.

    Kept as the plainest possible CBV (`View`, one `get()` method) — a raw
    CSS response with no form/model/template involved has no complexity a
    richer generic view would help with (Phase 03 FBV audit)."""

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        tokens = ThemeCacheService.get_active_tokens()
        css = render_theme_css(tokens) if tokens else ""
        response = HttpResponse(css, content_type="text/css")
        response["Cache-Control"] = "public, max-age=3600"
        return response
