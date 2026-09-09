"""Renders a validated tokens dict into CSS custom properties.

This is the other half of the CSS-injection defense: even though
apps.theme.validation already guaranteed every value matches an exact
allow-listed shape before it was saved, this module re-checks the same
patterns immediately before string interpolation — cheap, and it means a
future code path that writes `tokens` without going through the service
still can't get an injected value into a <style> response.
"""

from __future__ import annotations

from apps.theme.validation import (
    COLOR_TOKENS,
    RADIUS_TOKENS,
    is_valid_font_family,
    is_valid_hex_color,
    is_valid_size,
)

_CSS_VAR_NAME = {
    "brand": "--color-brand",
    "brand_hover": "--color-brand-hover",
    "brand_secondary": "--color-brand-secondary",
    "brand_accent": "--color-brand-accent",
    "background": "--color-background",
    "surface": "--color-surface",
    "text_primary": "--color-primary",
    "text_secondary": "--color-secondary",
    "border_default": "--color-default",
    "success": "--color-success",
    "warning": "--color-warning",
    "danger": "--color-danger",
    "info": "--color-info",
}

_RADIUS_VAR_NAME = {"sm": "--radius-sm", "md": "--radius-md", "lg": "--radius-lg"}

# Only these colors actually differ between light and dark in Phase 01's
# app.css (background/surface/text/border) — the brand/status palette stays
# constant across modes. Re-declaring every color in both blocks would be
# harmless but noisy; this keeps the generated CSS matching app.css's shape.
_MODE_VARYING_COLORS = {"background", "surface", "text_primary", "text_secondary", "border_default"}


def render_theme_css(tokens: dict) -> str:
    """Render a validated tokens dict as a standalone CSS string.

    Safe to call with any dict that already passed
    apps.theme.validation.validate_theme_tokens — anything that doesn't
    match the expected shape is silently skipped rather than interpolated,
    so a corrupted/legacy row degrades gracefully instead of producing
    unsafe CSS.
    """
    colors = tokens.get("colors", {})
    typography = tokens.get("typography", {})
    radius = tokens.get("radius", {})

    root_lines = []
    dark_media_lines = []
    dark_attr_lines = []

    for name in COLOR_TOKENS:
        value = colors.get(name)
        if not isinstance(value, dict):
            continue
        var_name = _CSS_VAR_NAME[name]
        light = value.get("light")
        dark = value.get("dark")

        if name in _MODE_VARYING_COLORS:
            if is_valid_hex_color(light):
                root_lines.append(f"  {var_name}: {light};")
            if is_valid_hex_color(dark):
                dark_media_lines.append(f"    {var_name}: {dark};")
                dark_attr_lines.append(f"  {var_name}: {dark};")
        else:
            # Constant across modes — light and dark are expected to match;
            # light is treated as authoritative if they ever differ.
            if is_valid_hex_color(light):
                root_lines.append(f"  {var_name}: {light};")

    font_family = typography.get("font_family")
    if is_valid_font_family(font_family):
        root_lines.append(f"  --font-sans: {font_family};")
    font_size_base = typography.get("font_size_base")
    if is_valid_size(font_size_base):
        root_lines.append(f"  --font-size-base: {font_size_base};")

    for name in RADIUS_TOKENS:
        value = radius.get(name)
        if is_valid_size(value):
            root_lines.append(f"  {_RADIUS_VAR_NAME[name]}: {value};")

    css_parts = [":root {", *root_lines, "}"]
    if dark_media_lines:
        css_parts += [
            "@media (prefers-color-scheme: dark) {",
            '  :root:not([data-theme="light"]) {',
            *dark_media_lines,
            "  }",
            "}",
        ]
    if dark_attr_lines:
        css_parts += [':root[data-theme="dark"] {', *dark_attr_lines, "}"]

    return "\n".join(css_parts) + "\n"
