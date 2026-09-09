"""Resolves which appearance (light/dark) to render server-side, so the
initial HTML response is already correct and there is nothing to flash —
see Phase 02 plan judgment call #6 and docs/frontend/theme-system.md.

Precedence:
    1. Authenticated user with an explicit "light"/"dark" preference wins —
       rendered directly as <html data-theme="...">.
    2. Anonymous, or an authenticated user whose preference is "system" (or
       who has no saved preference row): `resolved_appearance` is None, the
       template omits data-theme entirely, and the CSS
       `@media (prefers-color-scheme: dark)` rule already in app.css takes
       over natively — no JavaScript involved.
"""

from __future__ import annotations

from django.http import HttpRequest

from apps.theme.models import UserThemePreference


def appearance(request: HttpRequest) -> dict:
    resolved = None
    # hasattr guard matches django.contrib.auth.context_processors.auth —
    # a request that hasn't gone through AuthenticationMiddleware (e.g. a
    # RequestFactory request in a test, or an error page rendered before
    # middleware finished) has no .user at all.
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        preference = getattr(user, "theme_preference", None)
        if preference and preference.appearance != UserThemePreference.Appearance.SYSTEM:
            resolved = preference.appearance
    return {"resolved_appearance": resolved}
