"""Cross-cutting template context — nothing business-domain-specific.

`coming_soon_nav` is static UI data (the sidebar placeholders for domains
not built yet); it belongs in a context processor rather than being
threaded through every view's context by hand.
"""

from __future__ import annotations

from crispy_tailwind.tailwind import CSSContainer
from django.http import HttpRequest

COMING_SOON_NAV = [
    {"label": "Leave", "icon": "calendar-days"},
    {"label": "Attendance", "icon": "clock"},
    {"label": "Compensation", "icon": "banknote"},
    {"label": "Training", "icon": "graduation-cap"},
]


def navigation(request: HttpRequest) -> dict:
    return {"coming_soon_nav": COMING_SOON_NAV}


# crispy-tailwind looks for a `css_container` context variable and falls
# back to its own hardcoded gray-palette classes if none is supplied (see
# crispy_tailwind/templatetags/tailwind_field.py) — this is that override,
# so Django-rendered form fields (Input/Select/Textarea/Checkbox/Radio) use
# our semantic tokens instead. No template override needed for this.
_INPUT_CLASSES = (
    "block w-full appearance-none rounded-[var(--radius-input)] border border-default "
    "bg-surface px-3 py-2 text-sm text-primary placeholder:text-secondary "
    "focus:outline-none focus:ring-2 focus:ring-brand disabled:opacity-50"
)

CRISPY_CSS_CONTAINER = CSSContainer(
    {
        "base": _INPUT_CLASSES,
        "select": _INPUT_CLASSES,
        "checkbox": "h-4 w-4 rounded border-default accent-brand focus:ring-brand",
        "radioselect": "h-4 w-4 border-default accent-brand focus:ring-brand",
        "error_border": "border-danger",
    }
)


def crispy_theme(request: HttpRequest) -> dict:
    return {"css_container": CRISPY_CSS_CONTAINER}
