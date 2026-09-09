import copy

from apps.theme.rendering import render_theme_css
from apps.theme.validation import DEFAULT_THEME_TOKENS


def test_renders_valid_tokens_to_css_variables():
    css = render_theme_css(DEFAULT_THEME_TOKENS)
    assert "--color-brand: #DA291C;" in css
    assert ":root {" in css
    assert "@media (prefers-color-scheme: dark)" in css
    assert ':root[data-theme="dark"]' in css


def test_skips_a_malformed_value_instead_of_interpolating_it():
    """Defense-in-depth: even if something bypassed validate_theme_tokens
    and wrote an unsafe value directly, the renderer must never interpolate
    it into the CSS string (Phase 02 plan §4, §22-23)."""
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["colors"]["brand"]["light"] = "red; } body { background: url(javascript:alert(1))"

    css = render_theme_css(tokens)

    assert "javascript:" not in css
    assert "<script" not in css
    assert "alert(1)" not in css


def test_skips_malformed_font_family():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["typography"]["font_family"] = "Arial</style><script>alert(1)</script>"

    css = render_theme_css(tokens)

    assert "<script" not in css
    assert "--font-sans" not in css  # the whole declaration is skipped, not sanitized-in-place


def test_empty_tokens_render_empty_root_block():
    css = render_theme_css({})
    assert css.strip() == ":root {\n}"
