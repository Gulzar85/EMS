"""Foundation views: home shell, health checks, custom error pages.

No business logic lives here — this is purely technical-foundation glue.
See docs/architecture/application-architecture.md for the layering rules
this project follows once real domain apps exist.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

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


def health_live(request: HttpRequest) -> HttpResponse:
    """Process-is-up check — no dependency calls, safe for tight liveness probes."""
    return JsonResponse({"status": "alive"})


def health_ready(request: HttpRequest) -> HttpResponse:
    """Dependency check — database, and Redis only if REDIS_URL is configured."""
    checks = _run_health_checks(include_redis=True)
    return _render_health(request, checks)


def health(request: HttpRequest) -> HttpResponse:
    """Combined endpoint most monitors hit — same as /health/ready/."""
    return health_ready(request)


@login_required
def home(request: HttpRequest) -> HttpResponse:
    checks = _run_health_checks(include_redis=True)
    healthy = bool(checks) and all(value == "ok" for value in checks.values())
    context = {"status": "ok" if healthy else "error", "checks": checks}
    return render(request, "pages/home.html", context)


def custom_400(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "pages/errors/400.html", status=400)


def custom_403(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "pages/errors/403.html", status=403)


def custom_404(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "pages/errors/404.html", status=404)


def custom_500(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/errors/500.html", status=500)
