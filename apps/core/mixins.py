"""Small, genuinely cross-cutting CBV mixins — see docs/development/
coding-standards.md's guidance on not creating excessive one-off mixins.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404


class PublicIDLookupMixin:
    """Look a generic-view object up by `public_id` instead of the integer
    primary key — every URL-facing model in this project is addressed by
    `public_id` in URLs (see docs/adr/ADR-003-uuid-strategy.md), which
    Django's default SingleObjectMixin.get_object() doesn't know about.
    """

    def get_object(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        return get_object_or_404(queryset, public_id=self.kwargs["public_id"])


class HtmxTemplateMixin:
    """Return `partial_template_name` instead of the full-page template when
    the request came from htmx — same form/service/context, presentation
    only differs (Phase 02 plan §17-18)."""

    partial_template_name: str | None = None

    def get_template_names(self) -> list[str]:
        if self.partial_template_name and self.request.headers.get("HX-Request") == "true":
            return [self.partial_template_name]
        return super().get_template_names()


class HtmxRedirectMixin:
    """A successful mutation always redirects (Post/Redirect/Get). For a
    plain request that's a normal 302. For an htmx request it must be an
    `HX-Redirect` response instead — htmx otherwise follows a 3xx via its
    own XHR and swaps the target in place, which is wrong when the
    destination is a different full page (Phase 02 plan §17, §19).
    """

    def redirect(self, url: str) -> HttpResponse:
        if self.request.headers.get("HX-Request") == "true":
            return HttpResponse(status=200, headers={"HX-Redirect": url})
        return HttpResponseRedirect(url)
