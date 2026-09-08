"""Cross-cutting template context — nothing business-domain-specific.

`coming_soon_nav` is static UI data (the sidebar placeholders for domains
not built yet); it belongs in a context processor rather than being
threaded through every view's context by hand.
"""

from __future__ import annotations

from django.http import HttpRequest

COMING_SOON_NAV = [
    {"label": "Employees", "icon": "users"},
    {"label": "Organization", "icon": "building-2"},
    {"label": "Leave", "icon": "calendar-days"},
    {"label": "Attendance", "icon": "clock"},
    {"label": "Compensation", "icon": "banknote"},
    {"label": "Training", "icon": "graduation-cap"},
]


def navigation(request: HttpRequest) -> dict:
    return {"coming_soon_nav": COMING_SOON_NAV}
