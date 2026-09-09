import copy

import pytest

from apps.theme.exceptions import ThemeValidationError
from apps.theme.validation import DEFAULT_THEME_TOKENS, validate_theme_tokens


def test_default_tokens_are_valid():
    validate_theme_tokens(DEFAULT_THEME_TOKENS)  # must not raise


def test_rejects_non_dict_payload():
    with pytest.raises(ThemeValidationError):
        validate_theme_tokens("not a dict")


def test_rejects_unknown_top_level_key():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["shadows"] = {"sm": "0 1px 2px black"}
    with pytest.raises(ThemeValidationError, match="Unknown top-level"):
        validate_theme_tokens(tokens)


def test_rejects_wrong_schema_version():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["schema_version"] = 2
    with pytest.raises(ThemeValidationError, match="schema_version"):
        validate_theme_tokens(tokens)


def test_rejects_missing_color_token():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    del tokens["colors"]["brand"]
    with pytest.raises(ThemeValidationError, match="Missing color"):
        validate_theme_tokens(tokens)


def test_rejects_unknown_color_token():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["colors"]["extra"] = {"light": "#ffffff", "dark": "#000000"}
    with pytest.raises(ThemeValidationError, match="Unknown color"):
        validate_theme_tokens(tokens)


def test_rejects_color_missing_dark_variant():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["colors"]["brand"] = {"light": "#ffffff"}
    with pytest.raises(ThemeValidationError, match="light/dark"):
        validate_theme_tokens(tokens)


@pytest.mark.parametrize(
    "malicious_value",
    [
        "<script>alert(1)</script>",
        "javascript:alert(1)",
        "expression(alert(1))",
        "red; } body { background: url(javascript:alert(1))",
        "#fff; } * { color: red",
        "rgb(255,0,0)",
        "red",
        "#ff0000ff",  # 8-digit hex (with alpha) not allowed — exact 6-digit only
        "#fff",  # 3-digit shorthand not allowed
        "",
    ],
)
def test_rejects_malicious_or_malformed_color_values(malicious_value):
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["colors"]["brand"]["light"] = malicious_value
    with pytest.raises(ThemeValidationError):
        validate_theme_tokens(tokens)


@pytest.mark.parametrize(
    "malicious_family",
    [
        "Arial'; } body { background: url(javascript:alert(1)) } .x {",
        "Arial</style><script>alert(1)</script>",
        "Arial; background: url(evil.com)",
        "Arial{color:red}",
        "a" * 300,  # too long
    ],
)
def test_rejects_malicious_font_family(malicious_family):
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["typography"]["font_family"] = malicious_family
    with pytest.raises(ThemeValidationError):
        validate_theme_tokens(tokens)


@pytest.mark.parametrize("bad_size", ["16", "16em", "16px; } body {", "-16px", "16 px"])
def test_rejects_malformed_sizes(bad_size):
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["typography"]["font_size_base"] = bad_size
    with pytest.raises(ThemeValidationError):
        validate_theme_tokens(tokens)


def test_rejects_unknown_radius_token():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["radius"]["xl"] = "1rem"
    with pytest.raises(ThemeValidationError, match="Unknown radius"):
        validate_theme_tokens(tokens)


def test_accepts_valid_px_and_rem_sizes():
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["radius"]["sm"] = "4px"
    tokens["radius"]["md"] = "0.5rem"
    validate_theme_tokens(tokens)  # must not raise
