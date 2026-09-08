# Theme System — Implementation Mechanics

Status: Final (Phase 01 baseline)
Audience: Engineers implementing the theme system in code.

Related documents:
- [Theme Architecture](../architecture/theme-architecture.md) (the "why" — read this first)
- [Design System](design-system.md) (the token reference and light/dark rules)
- [Frontend Architecture](../architecture/frontend-architecture.md)

This document is the deep technical reference for **building** the theme system described conceptually in [theme-architecture.md](../architecture/theme-architecture.md). No code exists yet (this is a greenfield spec) — the shapes below are the intended design for Phase 01 implementation.

---

## 1. `ThemeConfiguration` Model — Field List

One model holds the entire theme. For Phase 01 (single active theme, no multi-tenant/multi-brand requirement yet), a single active row is assumed, enforced by convention (e.g. a `is_active` boolean with a uniqueness constraint, or simply `pk=1`); the shape still supports multiple rows later (e.g. per-brand theming) without a schema change.

Common, well-known tokens get **concrete fields** (typed, validated, editable as normal form fields in Theme Studio). Rare/future tokens go in a single JSONField `extra` so the system can grow without a migration for every new knob — `ThemeService` reads `extra` last, layering it over the concrete fields so an `extra` key can also override a known token.

```python
class ThemeConfiguration(models.Model):
    name = models.CharField(max_length=100, default="Default Theme")
    is_active = models.BooleanField(default=True)
    appearance_mode = models.CharField(
        max_length=10,
        choices=[("light", "Light"), ("dark", "Dark"), ("system", "System")],
        default="system",
    )

    # --- Colors (light / dark pairs) ---
    color_primary_light = models.CharField(max_length=7, default="#DA291C")
    color_primary_dark = models.CharField(max_length=7, default="#E5493C")
    color_primary_hover_light = models.CharField(max_length=7, default="#B52117")
    color_primary_hover_dark = models.CharField(max_length=7, default="#F16659")
    color_secondary_light = models.CharField(max_length=7, default="#FFC72C")
    color_secondary_dark = models.CharField(max_length=7, default="#FFD35C")
    color_accent_light = models.CharField(max_length=7, default="#27251F")
    color_accent_dark = models.CharField(max_length=7, default="#4A473F")
    color_background_light = models.CharField(max_length=7, default="#F7F7F5")
    color_background_dark = models.CharField(max_length=7, default="#15161A")
    color_surface_light = models.CharField(max_length=7, default="#FFFFFF")
    color_surface_dark = models.CharField(max_length=7, default="#1E2025")
    color_text_primary_light = models.CharField(max_length=7, default="#1A1A1A")
    color_text_primary_dark = models.CharField(max_length=7, default="#F2F2F2")
    color_text_secondary_light = models.CharField(max_length=7, default="#5A5A5A")
    color_text_secondary_dark = models.CharField(max_length=7, default="#A6A6A6")
    color_border_light = models.CharField(max_length=7, default="#E2E2E0")
    color_border_dark = models.CharField(max_length=7, default="#33353B")
    color_success_light = models.CharField(max_length=7, default="#1E8E3E")
    color_success_dark = models.CharField(max_length=7, default="#4CBB6E")
    color_warning_light = models.CharField(max_length=7, default="#B8860B")
    color_warning_dark = models.CharField(max_length=7, default="#E0AC3C")
    color_danger_light = models.CharField(max_length=7, default="#C62828")
    color_danger_dark = models.CharField(max_length=7, default="#E5534B")
    color_info_light = models.CharField(max_length=7, default="#1565C0")
    color_info_dark = models.CharField(max_length=7, default="#5B9BE0")

    # --- Typography ---
    font_family_base = models.CharField(
        max_length=200, default='"Inter", ui-sans-serif, system-ui, sans-serif'
    )
    font_size_base_rem = models.DecimalField(max_digits=4, decimal_places=3, default=0.9375)
    font_scale_ratio = models.DecimalField(max_digits=3, decimal_places=2, default=1.20)
    font_weight_normal = models.PositiveSmallIntegerField(default=400)
    font_weight_medium = models.PositiveSmallIntegerField(default=500)
    font_weight_bold = models.PositiveSmallIntegerField(default=700)
    line_height_base = models.DecimalField(max_digits=3, decimal_places=2, default=1.50)

    # --- Layout ---
    sidebar_width_rem = models.DecimalField(max_digits=4, decimal_places=2, default=16.00)
    sidebar_position = models.CharField(
        max_length=5, choices=[("left", "Left"), ("right", "Right")], default="left"
    )
    navbar_height_rem = models.DecimalField(max_digits=4, decimal_places=2, default=3.50)
    content_max_width_rem = models.DecimalField(max_digits=5, decimal_places=2, default=90.00)
    density = models.CharField(
        max_length=12,
        choices=[("compact", "Compact"), ("comfortable", "Comfortable")],
        default="comfortable",
    )

    # --- Components ---
    radius_button_rem = models.DecimalField(max_digits=4, decimal_places=3, default=0.375)
    radius_card_rem = models.DecimalField(max_digits=4, decimal_places=3, default=0.500)
    radius_input_rem = models.DecimalField(max_digits=4, decimal_places=3, default=0.375)
    radius_badge_rem = models.DecimalField(max_digits=4, decimal_places=3, default=999)  # pill
    shadow_sm = models.CharField(max_length=200, default="0 1px 2px rgba(0,0,0,0.05)")
    shadow_md = models.CharField(max_length=200, default="0 4px 6px rgba(0,0,0,0.07)")
    shadow_lg = models.CharField(max_length=200, default="0 10px 20px rgba(0,0,0,0.10)")
    border_width_default_px = models.PositiveSmallIntegerField(default=1)

    # --- Escape hatch for future/rare tokens ---
    extra = models.JSONField(default=dict, blank=True)

    version = models.PositiveIntegerField(
        default=1
    )  # bumped on every save; drives /theme.css cache-busting
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        self.version = (self.version or 0) + 1
        super().save(*args, **kwargs)
```

Notes:
- Color fields store `#RRGGBB` hex strings; the Theme Studio form uses native/Alpine-enhanced color pickers.
- Numeric layout/typography fields are stored as plain decimals in a known unit (rem/px) rather than raw CSS strings, so Theme Studio can render them as sliders/number inputs with validation (e.g. min/max sidebar width) — `ThemeService` appends the unit when rendering CSS.
- `extra` is a flat `{css_variable_name: value}` dict for tokens that don't yet have a dedicated field (e.g. a newly requested `--color-focus-ring` before it's promoted to a concrete field in a later migration).

---

## 2. `ThemeService.render_css_variables(theme) -> str`

Responsibility: pure transformation from a `ThemeConfiguration` instance to CSS text. No I/O, no caching, no HTTP concerns — those live in the view (§3).

```python
class ThemeService:
    @staticmethod
    def render_css_variables(theme: "ThemeConfiguration") -> str:
        """
        Build the full /theme.css body for a given ThemeConfiguration:
          - a base :root block using LIGHT values
          - a `@media (prefers-color-scheme: dark)` block using DARK values,
            scoped to :root:not([data-theme="light"]) so an explicit light
            override still wins over OS dark mode
          - a `:root[data-theme="dark"]` block using DARK values, so an
            explicit user choice wins unconditionally
          - `extra` keys layered on top of all three blocks as raw
            `--name: value;` declarations
        Returns a single string of valid CSS, ready to serve as text/css.
        """
```

Key responsibilities in full:
1. Map every concrete field to its CSS variable name (e.g. `color_primary_light` → `--color-primary`, `color_primary_dark` → `--color-primary` under the dark blocks).
2. Append units where the DB stores bare numbers (e.g. `sidebar_width_rem: 16.00` → `--layout-sidebar-width: 16rem;`).
3. Derive computed tokens that aren't stored directly but follow from stored ones (e.g. heading font sizes from `font_size_base_rem` × `font_scale_ratio^n`, or `--spacing-unit` from `density`).
4. Merge `extra` last, so it can add new variables or override any computed/concrete one without a schema change.
5. Never touches Tailwind, never shells out to Node — this is string building only, safe to run inline in a request/response cycle or a management command.

`ThemeService` also exposes `ThemeService.get_active_theme()` which returns the active `ThemeConfiguration` (cached — see §3) or the in-code `DEFAULT_THEME` fallback described in [theme-architecture.md](../architecture/theme-architecture.md) §5 if no row exists.

---

## 3. The `/theme.css` Django View

```python
def theme_css(request):
    theme = ThemeService.get_active_theme()
    css = ThemeService.render_css_variables(theme)
    response = HttpResponse(css, content_type="text/css")
    response["ETag"] = f'"{theme.version}"'
    if "v" in request.GET:
        # Versioned URL: content for this version never changes.
        response["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        # Bare URL fallback: short cache, always eventually fresh.
        response["Cache-Control"] = "public, max-age=60"
    return response
```

- `ThemeService.get_active_theme()` wraps the DB read in Django's cache framework (`cache.get_or_set("active_theme", ..., timeout=None)`), invalidated explicitly whenever `ThemeConfiguration.save()` runs (e.g. via a `post_save` signal calling `cache.delete("active_theme")`), so normal request traffic never hits the database for every page load.
- The view performs no writes and requires no special permission to **read** — it's a public, cacheable static-like asset. Only the Theme Studio **save** path (below) is permission-gated.

### Template tag

```python
@register.simple_tag
def theme_css_url():
    theme = ThemeService.get_active_theme()
    return f"{reverse('theme_css')}?v={theme.version}"
```

Used in `base.html` as:

```html
<link rel="stylesheet" href="{% theme_css_url %}">
```

Because the tag reads the current `version` on every render, any page rendered after a theme save automatically points at the new versioned URL — no manual cache-busting anywhere else in the codebase.

---

## 4. Permissions

- A dedicated permission, `theme.manage_theme` (a custom Django permission on `ThemeConfiguration`), gates the Theme Studio view (both viewing the edit form and saving). This is checked in addition to normal staff/superuser access, so an org can grant "can manage the visual theme" narrowly (e.g. to a Brand/Marketing admin) without granting broader system administration rights.
- The `/theme.css` read endpoint itself has no permission check — it must be loadable by every authenticated (and, for the login page's own styling, unauthenticated) request.

---

## 5. Theme Studio UX Flow

1. **Entry**: an admin with `theme.manage_theme` opens `/admin-tools/theme-studio/` (a dedicated view, not necessarily the Django admin app, so it can offer a richer live-preview layout).
2. **Form**: a single Django form (grouped into fieldsets matching §4 of [theme-architecture.md](../architecture/theme-architecture.md): Colors, Typography, Layout, Components, Appearance), rendered with crispy-tailwind like any other form in the system — Theme Studio's own form is styled by the theme it's editing, which is a deliberate "eat your own dog food" check.
3. **Live preview (no save required)**: the form page includes a preview pane (a panel showing sample components — a button, a card, a badge, a small table) rendered via the same `components/*` templates used app-wide. Every field change (color picker `input`/`change` event, slider `input` event) triggers an HTMX request (`hx-post` to a `theme_preview` view, debounced client-side via Alpine, e.g. `hx-trigger="change delay:200ms"`) that:
   - Takes the **current in-browser form values** (not yet saved),
   - Runs them through `ThemeService.render_css_variables()` against a transient, unsaved `ThemeConfiguration(**posted_values)` instance (never calling `.save()`),
   - Returns a `<style>` block (or a fresh `/theme-preview.css`-style inline response) scoped to `#theme-preview-pane`, plus the same sample-components partial, so the admin sees an accurate, live rendering of buttons/cards/badges/tables under the *candidate* theme before committing.
   - This preview path deliberately reuses `ThemeService` (never a separate rendering codepath), so what the admin previews is guaranteed to match what `/theme.css` will produce once saved.
4. **Save**: a distinct "Save" action performs the real `ThemeConfiguration.save()` (persisting values and bumping `version` per the model's overridden `save()`), invalidates the `active_theme` cache key, and redirects back to Theme Studio with a success Alert. From this point, every page in the app (not just the preview pane) reflects the new theme on next load, because `{% theme_css_url %}` now resolves to the new version.
5. **Contrast safety net**: when rendering the live preview, the view additionally computes a basic WCAG contrast ratio for a few key pairs (text-primary on background, text-on-primary on primary) and surfaces a Warning-styled inline note in the preview pane if a pair falls below AA — informational only, does not block saving, since brand requirements may sometimes need to override the tool's own recommendation.

---

## 6. Seeding Defaults — Never Unstyled

The defaults tabulated in [theme-architecture.md](../architecture/theme-architecture.md) §4 ship as a **data migration** (preferred, since it runs automatically and exactly once as part of `manage.py migrate` in every environment):

```python
def seed_default_theme(apps, schema_editor):
    ThemeConfiguration = apps.get_model("theming", "ThemeConfiguration")
    if not ThemeConfiguration.objects.exists():
        ThemeConfiguration.objects.create(name="Default Theme", is_active=True)
        # all other fields take their model-level defaults


class Migration(migrations.Migration):
    dependencies = [("theming", "0001_initial")]
    operations = [migrations.RunPython(seed_default_theme, migrations.RunPython.noop)]
```

A fixture (`theming/fixtures/default_theme.json`) is kept as an alternative/documentation-friendly form of the same seed data for local dev resets (`loaddata`), but the data migration is what guarantees production and every fresh environment always has a valid, active `ThemeConfiguration` row immediately after deploy — combined with `ThemeService`'s in-code `DEFAULT_THEME` fallback (§2, and [theme-architecture.md](../architecture/theme-architecture.md) §5) for the narrow edge case of `/theme.css` being requested before migrations have run, the application never renders unstyled.
