"""Seeds one published, active Theme so the pipeline works end-to-end from
first migration. Tokens are inlined (not imported from apps.theme.validation)
because data migrations should be frozen in time, independent of
application code that may change later — see docs/development/
theme-development.md.

app.css's hardcoded @theme block remains the ultimate fallback regardless
(if this row is ever deleted, /theme.css just serves nothing and the
hardcoded CSS defaults take over).
"""

from django.db import migrations

DEFAULT_THEME_TOKENS = {
    "schema_version": 1,
    "colors": {
        "brand": {"light": "#da291c", "dark": "#da291c"},
        "brand_hover": {"light": "#b72116", "dark": "#b72116"},
        "brand_secondary": {"light": "#27251f", "dark": "#27251f"},
        "brand_accent": {"light": "#ffc72c", "dark": "#ffc72c"},
        "background": {"light": "#f7f7f5", "dark": "#111827"},
        "surface": {"light": "#ffffff", "dark": "#1f2937"},
        "text_primary": {"light": "#1f2937", "dark": "#f3f4f6"},
        "text_secondary": {"light": "#6b7280", "dark": "#9ca3af"},
        "border_default": {"light": "#e5e7eb", "dark": "#374151"},
        "success": {"light": "#16a34a", "dark": "#16a34a"},
        "warning": {"light": "#d97706", "dark": "#d97706"},
        "danger": {"light": "#dc2626", "dark": "#dc2626"},
        "info": {"light": "#2563eb", "dark": "#2563eb"},
    },
    "typography": {
        "font_family": "'Inter', ui-sans-serif, system-ui, sans-serif",
        "font_size_base": "16px",
    },
    "radius": {"sm": "0.375rem", "md": "0.5rem", "lg": "0.75rem"},
}


def seed_default_theme(apps, schema_editor):
    Theme = apps.get_model("theme", "Theme")
    ThemeVersion = apps.get_model("theme", "ThemeVersion")

    from django.utils import timezone

    theme = Theme.objects.create(
        name="McDonald's Pakistan Default",
        description="The seeded default theme, matching the original hardcoded app.css values.",
        is_active=True,
    )
    version = ThemeVersion.objects.create(
        theme=theme,
        version_number=1,
        status="published",
        schema_version=1,
        tokens=DEFAULT_THEME_TOKENS,
        published_at=timezone.now(),
    )
    theme.active_version = version
    theme.save(update_fields=["active_version"])


def unseed_default_theme(apps, schema_editor):
    Theme = apps.get_model("theme", "Theme")
    Theme.objects.filter(name="McDonald's Pakistan Default").delete()


class Migration(migrations.Migration):
    dependencies = [("theme", "0001_initial")]

    operations = [migrations.RunPython(seed_default_theme, unseed_default_theme)]
