"""Foundation views: home shell, health checks, custom error pages.

No business logic lives here — this is purely technical-foundation glue.
See docs/architecture/application-architecture.md for the layering rules
this project follows once real domain apps exist.

Every view here is class-based (Phase 03's absolute CBV requirement).
Health checks and error pages use the plainest possible CBV (`View`) —
there is no form/model/template complexity that would benefit from a
richer generic view; forcing one on would be the over-engineering Phase
03 §95 itself warns against. See the Phase 03 plan's FBV audit for the
full before/after list.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db import connection
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

logger = logging.getLogger("ems")


def _run_health_checks(*, include_redis: bool) -> dict[str, str]:
    checks: dict[str, str] = {}

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except OperationalError:
        logger.warning("Health check: database unreachable")
        checks["database"] = "unreachable"

    if include_redis and getattr(settings, "REDIS_URL", None):
        try:
            cache.set("health_check_probe", "1", timeout=5)
            checks["redis"] = "ok" if cache.get("health_check_probe") == "1" else "unreachable"
        except Exception:  # pragma: no cover - defensive, cache backend specific
            logger.warning("Health check: redis unreachable")
            checks["redis"] = "unreachable"

    return checks


def _render_health(request: HttpRequest, checks: dict[str, str]) -> HttpResponse:
    healthy = bool(checks) and all(value == "ok" for value in checks.values())
    status_code = 200 if healthy else 503
    context = {"status": "ok" if healthy else "error", "checks": checks}

    if request.headers.get("HX-Request") == "true":
        return render(request, "partials/_health_status.html", context, status=status_code)

    # Deliberately NOT using request.accepts("text/html") here: an absent
    # Accept header (the common case for curl / uptime monitors) resolves to
    # "*/*", which text/html always matches — that would silently send
    # monitoring probes a full HTML page instead of JSON. Only real browser
    # navigation sends "text/html" explicitly, so require that literally.
    if "text/html" in request.headers.get("Accept", ""):
        return render(request, "pages/health.html", context, status=status_code)
    return JsonResponse(context, status=status_code)


class HealthLiveView(View):
    """Process-is-up check — no dependency calls, safe for tight liveness probes."""

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return JsonResponse({"status": "alive"})


class HealthReadyView(View):
    """Dependency check — database, and Redis only if REDIS_URL is configured."""

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        checks = _run_health_checks(include_redis=True)
        return _render_health(request, checks)


class HealthView(HealthReadyView):
    """Combined endpoint most monitors hit — same as /health/ready/."""


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        checks = _run_health_checks(include_redis=True)
        healthy = bool(checks) and all(value == "ok" for value in checks.values())
        context["status"] = "ok" if healthy else "error"
        context["checks"] = checks
        return context


class ErrorView(TemplateView):
    """One shared CBV for all four error pages, parametrized per-handler in
    config/urls.py via `.as_view(template_name=..., status_code=...)` —
    exactly what Django's `.as_view(**initkwargs)` mechanism is for, not
    four near-identical view classes.

    Django invokes handler400/403/404/500 with the *original* request
    object — whatever HTTP method triggered the error (a PermissionDenied
    raised while handling a POST, say, must still render a 403 page, not
    fall through to TemplateView's GET-only default and produce a bare
    405). `dispatch()` is overridden to render unconditionally regardless
    of method, rather than exposing `post`/`put`/`delete` aliases.
    """

    status_code = 500

    def dispatch(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def render_to_response(self, context, **response_kwargs):
        response_kwargs.setdefault("status", self.status_code)
        return super().render_to_response(context, **response_kwargs)
