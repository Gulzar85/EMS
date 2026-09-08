"""A small, dependency-free icon strategy.

Renders vendored Lucide SVGs (apps/core/static/core/icons/*.svg, ISC
licensed, see docs/development/frontend.md) inline, so templates never need
to paste large SVG blobs and there's no JS-based icon-swap flash of
unstyled content.

Usage:
    {% load icons %}
    {% icon "menu" %}
    {% icon "chevron-down" size=16 class_name="text-secondary" %}

("class_name" rather than "class" — `class` is a reserved Python keyword
and can't be a keyword argument name.)
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ICONS_DIR = Path(__file__).resolve().parent.parent / "static" / "core" / "icons"

_SVG_INNER_RE = re.compile(r"<svg[^>]*>(.*?)</svg>", re.DOTALL)


@cache
def _load_icon_inner(name: str) -> str:
    path = ICONS_DIR / f"{name}.svg"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    match = _SVG_INNER_RE.search(raw)
    return match.group(1).strip() if match else ""


@register.simple_tag
def icon(name: str, size: int = 24, class_name: str = "") -> str:
    inner = _load_icon_inner(name)
    if not inner:
        return ""
    css_class = f"lucide-icon {class_name}".strip()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" class="{css_class}" '
        f'aria-hidden="true" focusable="false">{inner}</svg>'
    )
    return mark_safe(svg)
