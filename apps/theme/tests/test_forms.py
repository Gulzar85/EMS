import pytest

from apps.theme.forms import ThemeRollbackForm, ThemeStudioForm
from apps.theme.models import ThemeVersion
from apps.theme.tests.factories import ThemeFactory, ThemeVersionFactory
from apps.theme.validation import COLOR_TOKENS, DEFAULT_THEME_TOKENS

pytestmark = pytest.mark.django_db


def _valid_studio_data() -> dict:
    data = {"font_family": "'Inter', sans-serif", "font_size_base": "16px"}
    for name in COLOR_TOKENS:
        data[f"color_{name}_light"] = "#123456"
        data[f"color_{name}_dark"] = "#654321"
    for name in ("sm", "md", "lg"):
        data[f"radius_{name}"] = "0.5rem"
    return data


def test_studio_form_valid_data_produces_correct_tokens_dict():
    form = ThemeStudioForm(_valid_studio_data())
    assert form.is_valid(), form.errors
    assert form.cleaned_tokens["colors"]["brand"] == {"light": "#123456", "dark": "#654321"}
    assert form.cleaned_tokens["typography"]["font_family"] == "'Inter', sans-serif"
    assert form.cleaned_tokens["radius"]["sm"] == "0.5rem"
    assert form.cleaned_tokens["schema_version"] == 1


def test_studio_form_rejects_invalid_hex_color():
    data = _valid_studio_data()
    data["color_brand_light"] = "not-a-color"
    form = ThemeStudioForm(data)
    assert not form.is_valid()
    assert "color_brand_light" in form.errors


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        "javascript:alert(1)",
        "red; } body { background: url(javascript:alert(1))",
    ],
)
def test_studio_form_rejects_malicious_color_payloads(payload):
    data = _valid_studio_data()
    data["color_brand_light"] = payload
    form = ThemeStudioForm(data)
    assert not form.is_valid()


def test_studio_form_rejects_malicious_font_family():
    data = _valid_studio_data()
    data["font_family"] = "Arial</style><script>alert(1)</script>"
    form = ThemeStudioForm(data)
    assert not form.is_valid()
    assert "font_family" in form.errors


def test_studio_form_missing_fields_is_invalid():
    form = ThemeStudioForm({})
    assert not form.is_valid()


def test_studio_form_from_tokens_round_trips():
    form = ThemeStudioForm.from_tokens(DEFAULT_THEME_TOKENS)
    assert form.initial["color_brand_light"] == DEFAULT_THEME_TOKENS["colors"]["brand"]["light"]
    assert form.initial["font_family"] == DEFAULT_THEME_TOKENS["typography"]["font_family"]


def test_rollback_form_only_offers_published_versions_excluding_active():
    theme = ThemeFactory()
    published = ThemeVersionFactory(
        theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED
    )
    active = ThemeVersionFactory(
        theme=theme, version_number=2, status=ThemeVersion.Status.PUBLISHED
    )
    ThemeVersionFactory(theme=theme, version_number=3, status=ThemeVersion.Status.DRAFT)
    theme.active_version = active
    theme.save(update_fields=["active_version"])

    form = ThemeRollbackForm(theme=theme)
    offered = list(form.fields["target_version"].queryset)

    assert offered == [published]
