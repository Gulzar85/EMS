"""Theme forms — the authoritative validation boundary (server-side is
authoritative; any client-side checks are UX only, never duplicated logic).
"""

from __future__ import annotations

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout
from django import forms

from apps.theme.exceptions import ThemeValidationError
from apps.theme.models import Theme, ThemeVersion, UserThemePreference
from apps.theme.validation import (
    COLOR_TOKENS,
    CURRENT_SCHEMA_VERSION,
    RADIUS_TOKENS,
    is_valid_font_family,
    is_valid_hex_color,
    is_valid_size,
    validate_theme_tokens,
)


class ThemeForm(forms.ModelForm):
    class Meta:
        model = Theme
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ThemeCreateForm(ThemeForm):
    """Used by ThemeCreateView — the view calls ThemeService.create_theme()
    with the cleaned data rather than form.save(), since creating a Theme
    also creates its first draft version (not plain single-model CRUD)."""


class ThemeUpdateForm(ThemeForm):
    """Metadata-only edit (name/description) — this one IS plain CRUD, so
    the view may use form.save() directly."""


class ThemeStudioForm(forms.Form):
    """Flat, per-token fields (rather than one opaque JSON blob) so each
    token gets its own label and its own field-level error message. Color
    fields are generated in __init__ from COLOR_TOKENS to avoid 26 lines
    of boilerplate.
    """

    font_family = forms.CharField(
        max_length=200,
        label="Font family",
        widget=forms.TextInput(attrs={"data-preview-typography": "font_family"}),
    )
    font_size_base = forms.CharField(
        max_length=20,
        label="Base font size",
        widget=forms.TextInput(attrs={"data-preview-typography": "font_size_base"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # data-preview-* attributes drive the live preview in
        # static/src/js/components/theme-studio.js — it reads them via
        # event delegation rather than parsing field names, since a token
        # name like "brand_hover" makes "color_{token}_{mode}" ambiguous
        # to split back apart.
        for name in COLOR_TOKENS:
            label = name.replace("_", " ").title()
            self.fields[f"color_{name}_light"] = forms.CharField(
                max_length=7,
                label=f"{label} — light",
                widget=forms.TextInput(
                    attrs={
                        "type": "color",
                        "data-preview-color": name,
                        "data-preview-mode": "light",
                    }
                ),
            )
            self.fields[f"color_{name}_dark"] = forms.CharField(
                max_length=7,
                label=f"{label} — dark",
                widget=forms.TextInput(
                    attrs={"type": "color", "data-preview-color": name, "data-preview-mode": "dark"}
                ),
            )
        for name in RADIUS_TOKENS:
            self.fields[f"radius_{name}"] = forms.CharField(
                max_length=20,
                label=f"Radius — {name}",
                widget=forms.TextInput(attrs={"data-preview-radius": name}),
            )

        color_fields = [
            field
            for name in COLOR_TOKENS
            for field in (f"color_{name}_light", f"color_{name}_dark")
        ]
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset("Colors", *color_fields),
            Fieldset("Typography", "font_family", "font_size_base"),
            Fieldset("Radius", "radius_sm", "radius_md", "radius_lg"),
        )

    @classmethod
    def from_tokens(cls, tokens: dict, **kwargs) -> ThemeStudioForm:
        colors = tokens.get("colors", {})
        typography = tokens.get("typography", {})
        radius = tokens.get("radius", {})

        initial = {
            "font_family": typography.get("font_family", ""),
            "font_size_base": typography.get("font_size_base", ""),
        }
        for name in COLOR_TOKENS:
            value = colors.get(name, {})
            initial[f"color_{name}_light"] = value.get("light", "")
            initial[f"color_{name}_dark"] = value.get("dark", "")
        for name in RADIUS_TOKENS:
            initial[f"radius_{name}"] = radius.get(name, "")
        return cls(initial=initial, **kwargs)

    def clean(self):
        cleaned = super().clean()
        tokens = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "colors": {},
            "typography": {},
            "radius": {},
        }

        for name in COLOR_TOKENS:
            light_field, dark_field = f"color_{name}_light", f"color_{name}_dark"
            light, dark = cleaned.get(light_field), cleaned.get(dark_field)
            valid = True
            if light and not is_valid_hex_color(light):
                self.add_error(light_field, "Enter a valid hex color, e.g. #DA291C.")
                valid = False
            if dark and not is_valid_hex_color(dark):
                self.add_error(dark_field, "Enter a valid hex color, e.g. #DA291C.")
                valid = False
            if valid and light and dark:
                tokens["colors"][name] = {"light": light.lower(), "dark": dark.lower()}

        font_family = cleaned.get("font_family")
        if font_family and not is_valid_font_family(font_family):
            self.add_error(
                "font_family",
                "Only letters, numbers, spaces, commas, hyphens and quotes are allowed.",
            )
        elif font_family:
            tokens["typography"]["font_family"] = font_family

        font_size_base = cleaned.get("font_size_base")
        if font_size_base and not is_valid_size(font_size_base):
            self.add_error("font_size_base", "Use a plain size like 16px or 1rem.")
        elif font_size_base:
            tokens["typography"]["font_size_base"] = font_size_base

        for name in RADIUS_TOKENS:
            field_name = f"radius_{name}"
            value = cleaned.get(field_name)
            if value and not is_valid_size(value):
                self.add_error(field_name, "Use a plain size like 0.5rem or 8px.")
            elif value:
                tokens["radius"][name] = value

        if not self.errors:
            try:
                validate_theme_tokens(tokens)
            except ThemeValidationError as exc:
                raise forms.ValidationError(str(exc)) from exc
            self.cleaned_tokens = tokens

        return cleaned


class ThemePublishForm(forms.Form):
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ThemeRollbackForm(forms.Form):
    target_version = forms.ModelChoiceField(
        queryset=ThemeVersion.objects.none(), label="Roll back to"
    )
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, theme: Theme, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_version"].queryset = (
            theme.versions.filter(status=ThemeVersion.Status.PUBLISHED)
            .exclude(pk=theme.active_version_id)
            .order_by("-version_number")
        )


class ThemeDuplicateForm(forms.Form):
    new_name = forms.CharField(max_length=100, label="New theme name")


class AppearanceForm(forms.Form):
    appearance = forms.ChoiceField(choices=UserThemePreference.Appearance.choices)
