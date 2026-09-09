"""Strict, allow-list validation of theme token JSON.

This is the entire CSS-injection defense for the theme engine (see §22-23
of the Phase 02 brief and docs/security/theme-security.md): every value
that can ever reach a generated <style>/CSS response must first pass one
of these exact-shape regexes. There is no blocklist anywhere in this
module — allow-lists can't be bypassed by a payload the author didn't
think of, which a blocklist for `<script>`/`javascript:`/`expression(`/
`url(` etc. always can be.

Deliberately hand-rolled rather than the `jsonschema` package: the schema
is small, fixed, and known ahead of time (colors/typography/radius only —
nothing in app.css is parameterized beyond that yet), so a ~70-line
allow-list validator is simpler to read and audit than generic schema
machinery would be.
"""

from __future__ import annotations

import re
from typing import Any

from apps.theme.exceptions import ThemeValidationError

CURRENT_SCHEMA_VERSION = 1

COLOR_TOKENS: list[str] = [
    "brand",
    "brand_hover",
    "brand_secondary",
    "brand_accent",
    "background",
    "surface",
    "text_primary",
    "text_secondary",
    "border_default",
    "success",
    "warning",
    "danger",
    "info",
]

RADIUS_TOKENS: list[str] = ["sm", "md", "lg"]

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_FONT_FAMILY_RE = re.compile(r"^[A-Za-z0-9 ,'\-]{1,200}$")
_SIZE_RE = re.compile(r"^\d+(\.\d+)?(px|rem)$")

_KNOWN_TOP_LEVEL_KEYS = {"schema_version", "colors", "typography", "radius"}
_KNOWN_TYPOGRAPHY_KEYS = {"font_family", "font_size_base"}


def is_valid_hex_color(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX_COLOR_RE.match(value))


def is_valid_font_family(value: Any) -> bool:
    return isinstance(value, str) and bool(_FONT_FAMILY_RE.match(value))


def is_valid_size(value: Any) -> bool:
    return isinstance(value, str) and bool(_SIZE_RE.match(value))


def validate_theme_tokens(data: Any) -> None:
    """Raise ThemeValidationError (with a field-path message) on anything
    that doesn't exactly match the known schema. Passing means every value
    in `data` is safe to interpolate directly into generated CSS.
    """
    if not isinstance(data, dict):
        raise ThemeValidationError("Theme tokens must be a JSON object.")

    unknown = set(data) - _KNOWN_TOP_LEVEL_KEYS
    if unknown:
        raise ThemeValidationError(f"Unknown top-level section(s): {', '.join(sorted(unknown))}")

    if data.get("schema_version") != CURRENT_SCHEMA_VERSION:
        raise ThemeValidationError(
            f"schema_version must be {CURRENT_SCHEMA_VERSION}, got {data.get('schema_version')!r}."
        )

    _validate_colors(data.get("colors"))
    _validate_typography(data.get("typography"))
    _validate_radius(data.get("radius"))


def _validate_colors(colors: Any) -> None:
    if not isinstance(colors, dict):
        raise ThemeValidationError("colors section must be a JSON object.")

    unknown = set(colors) - set(COLOR_TOKENS)
    if unknown:
        raise ThemeValidationError(f"Unknown color token(s): {', '.join(sorted(unknown))}")
    missing = set(COLOR_TOKENS) - set(colors)
    if missing:
        raise ThemeValidationError(f"Missing color token(s): {', '.join(sorted(missing))}")

    for name, value in colors.items():
        if not isinstance(value, dict) or set(value) != {"light", "dark"}:
            raise ThemeValidationError(
                f"colors.{name} must be an object with exactly light/dark keys."
            )
        for mode in ("light", "dark"):
            if not is_valid_hex_color(value[mode]):
                raise ThemeValidationError(
                    f"colors.{name}.{mode} must be a #RRGGBB hex color, got {value[mode]!r}."
                )


def _validate_typography(typography: Any) -> None:
    if not isinstance(typography, dict):
        raise ThemeValidationError("typography section must be a JSON object.")

    unknown = set(typography) - _KNOWN_TYPOGRAPHY_KEYS
    if unknown:
        raise ThemeValidationError(f"Unknown typography key(s): {', '.join(sorted(unknown))}")
    missing = _KNOWN_TYPOGRAPHY_KEYS - set(typography)
    if missing:
        raise ThemeValidationError(f"Missing typography key(s): {', '.join(sorted(missing))}")

    if not is_valid_font_family(typography["font_family"]):
        raise ThemeValidationError("typography.font_family contains disallowed characters.")
    if not is_valid_size(typography["font_size_base"]):
        raise ThemeValidationError("typography.font_size_base must be a plain px/rem size.")


def _validate_radius(radius: Any) -> None:
    if not isinstance(radius, dict):
        raise ThemeValidationError("radius section must be a JSON object.")

    unknown = set(radius) - set(RADIUS_TOKENS)
    if unknown:
        raise ThemeValidationError(f"Unknown radius token(s): {', '.join(sorted(unknown))}")
    missing = set(RADIUS_TOKENS) - set(radius)
    if missing:
        raise ThemeValidationError(f"Missing radius token(s): {', '.join(sorted(missing))}")

    for name, value in radius.items():
        if not is_valid_size(value):
            raise ThemeValidationError(f"radius.{name} must be a plain px/rem size, got {value!r}.")


DEFAULT_THEME_TOKENS: dict[str, Any] = {
    "schema_version": CURRENT_SCHEMA_VERSION,
    "colors": {
        "brand": {"light": "#DA291C", "dark": "#DA291C"},
        "brand_hover": {"light": "#B72116", "dark": "#B72116"},
        "brand_secondary": {"light": "#27251F", "dark": "#27251F"},
        "brand_accent": {"light": "#FFC72C", "dark": "#FFC72C"},
        "background": {"light": "#F7F7F5", "dark": "#111827"},
        "surface": {"light": "#FFFFFF", "dark": "#1F2937"},
        "text_primary": {"light": "#1F2937", "dark": "#F3F4F6"},
        "text_secondary": {"light": "#6B7280", "dark": "#9CA3AF"},
        "border_default": {"light": "#E5E7EB", "dark": "#374151"},
        "success": {"light": "#16A34A", "dark": "#16A34A"},
        "warning": {"light": "#D97706", "dark": "#D97706"},
        "danger": {"light": "#DC2626", "dark": "#DC2626"},
        "info": {"light": "#2563EB", "dark": "#2563EB"},
    },
    "typography": {
        "font_family": "'Inter', ui-sans-serif, system-ui, sans-serif",
        "font_size_base": "16px",
    },
    "radius": {"sm": "0.375rem", "md": "0.5rem", "lg": "0.75rem"},
}
