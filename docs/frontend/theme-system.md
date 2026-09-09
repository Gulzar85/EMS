# Theme System — Implementation Mechanics

Status: **Implemented (Phase 02)** — supersedes the Phase 00/01 speculative design that lived in this file (a flat `ThemeConfiguration` model with ~40 concrete fields). Building the real thing surfaced a better shape: versioned tokens, not a giant flat model. See [ADR-006](../adr/ADR-006-dynamic-theme-architecture.md) for the original rationale, still valid; this document describes what was actually built.

Related documents:
- [Theme Architecture](../architecture/theme-architecture.md) — the "why"
- [Design System](design-system.md) — the token reference and light/dark rules
- [Theme Security](theme-security.md) — the CSS-injection defense in detail
- [Theme Development](../development/theme-development.md) — how to extend the schema

---

## 1. Why versioned tokens instead of one flat model

The Phase 00 plan sketched a single `ThemeConfiguration` row with ~40 concrete typed fields (`color_primary_light`, `sidebar_width_rem`, ...). Building Theme Studio's actual requirements — draft/publish/rollback, immutable history, "who published this and why" — made a **versioned** model the right fit instead: `Theme` (metadata + which version is live) → `ThemeVersion` (an immutable, timestamped snapshot of the full token set once published). A flat model has no natural place to keep old values around for rollback without inventing a second history table; the version table *is* the history.

## 2. Models (`apps/theme/models.py`)

```python
class Theme(TimeStampedModel, PublicIDModel):
    name = CharField(max_length=100, unique=True)
    description = TextField(blank=True)
    is_active = BooleanField(default=False)
    active_version = FK("ThemeVersion", null=True, on_delete=SET_NULL, related_name="+")
    created_by = FK(User, null=True, on_delete=SET_NULL, related_name="+")

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["is_active"], condition=Q(is_active=True), name="theme_single_active"
            ),
        ]
        permissions = [
            ("publish_theme", "Can publish a theme version"),
            ("rollback_theme", "Can roll back a theme"),
            ("activate_theme", "Can activate a theme"),
        ]


class ThemeVersion(TimeStampedModel, PublicIDModel):
    theme = FK(Theme, on_delete=CASCADE, related_name="versions")
    version_number = PositiveIntegerField()
    status = CharField(choices=[("draft", "Draft"), ("published", "Published")], default="draft")
    schema_version = PositiveIntegerField(default=1)
    tokens = JSONField()
    published_at = DateTimeField(null=True)
    published_by = FK(User, null=True, on_delete=SET_NULL, related_name="+")

    class Meta:
        constraints = [
            UniqueConstraint(fields=["theme", "version_number"], name="uniq_theme_version_number")
        ]

    def save(self, *args, **kwargs):
        # Refuses to change status/tokens on an already-PUBLISHED row —
        # published versions are immutable even via Django admin.
        ...


class UserThemePreference(TimeStampedModel):
    user = OneToOneField(User, primary_key=True, on_delete=CASCADE, related_name="theme_preference")
    appearance = CharField(
        choices=[("light", ...), ("dark", ...), ("system", ...)], default="system"
    )
```

**Concurrency**: exactly one `Theme` may have `is_active=True` — enforced by a Postgres partial unique index, not just application logic, so two admins publishing at once fail safely at the database rather than racing into an inconsistent state. Every service that flips `is_active` or `active_version` also wraps in `transaction.atomic()` with `select_for_update()`, so the common case never even reaches that race.

## 3. Token schema (`apps/theme/validation.py`)

```json
{
  "schema_version": 1,
  "colors": {
    "brand": {"light": "#DA291C", "dark": "#DA291C"},
    "brand_hover": {...}, "brand_secondary": {...}, "brand_accent": {...},
    "background": {...}, "surface": {...},
    "text_primary": {...}, "text_secondary": {...}, "border_default": {...},
    "success": {...}, "warning": {...}, "danger": {...}, "info": {...}
  },
  "typography": {"font_family": "'Inter', ui-sans-serif, system-ui, sans-serif", "font_size_base": "16px"},
  "radius": {"sm": "0.375rem", "md": "0.5rem", "lg": "0.75rem"}
}
```

Every color stores **both** a `light` and `dark` value in the same key — Phase 01's `app.css` already models dark mode as alternate values of the same CSS variables, so this mirrors that exactly. `validate_theme_tokens()` hand-validates every value against a strict regex (`^#[0-9a-fA-F]{6}$` for colors, an allow-list character class for font family, `^\d+(\.\d+)?(px|rem)$` for sizes) and rejects any top-level or color key outside the known closed set. See [theme-security.md](theme-security.md) for why this is hand-rolled rather than the `jsonschema` package, and exactly what it defends against.

To add a new token: add it to `COLOR_TOKENS`/`RADIUS_TOKENS` (or a new section) in `validation.py`, add its CSS variable mapping in `rendering.py`, add the corresponding field(s) in `ThemeStudioForm.__init__`, bump `CURRENT_SCHEMA_VERSION` only if the change isn't backward-compatible with existing published `ThemeVersion` rows. See [theme-development.md](../development/theme-development.md).

## 4. Rendering (`apps/theme/rendering.py`)

`render_theme_css(tokens: dict) -> str` builds the exact same three-block shape Phase 01 hand-wrote into `app.css`:

```css
:root { --color-brand: #DA291C; ... }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --color-background: #111827; ... }
}
:root[data-theme="dark"] { --color-background: #111827; ... }
```

Every value is re-validated against the same regexes immediately before string interpolation — defense-in-depth, in case some future code path ever writes `tokens` without going through the service layer (e.g. a data migration or a bulk-admin script).

## 5. Caching (`ThemeCacheService` in `apps/theme/services.py`)

Cache-aside on one key, `theme:active:tokens`, storing `{"version_id": ..., "tokens": ...}` — bundled together so the `/theme.css` view and the `{% theme_css_url %}` cache-busting tag (§6) share one cache read instead of two, and can never disagree with each other mid-request. Uses Django's configured cache (Redis if `REDIS_URL` is set, else local memory — Phase 01's existing setting, no new infrastructure). Every service call that changes which version is live calls `transaction.on_commit(ThemeCacheService.invalidate)` — `on_commit`, not an immediate `cache.delete()`, so a rolled-back transaction never leaves a stale-but-invalidated cache.

## 6. The `/theme.css` endpoint (`apps/theme/views.py: theme_css_view`)

A plain function view (the one deliberate FBV in this app — a raw `text/css` response with no template, no form, no auth, matching Phase 02's own guidance to use an FBV for "very specialized behavior that would become unnatural as a CBV"). Public and unauthenticated (needed by the login page itself), `Cache-Control: public, max-age=3600`, and always reachable at the bare `/theme.css` — the actual cache-busting happens via the query string:

```python
@register.simple_tag
def theme_css_url() -> str:
    version_id = ThemeCacheService.get_active_version_id() or 0
    return f"{reverse('theme-css')}?v={version_id}"
```

`base/blank.html` loads `app.css` first (the hardcoded Tailwind `@theme` defaults), then `{% theme_css_url %}` second, so the cascade lets the dynamic values win over the static fallback — and if no `Theme` is ever published, `/theme.css` simply returns an empty body and the hardcoded defaults keep working, exactly like Phase 01.

## 7. Publish / Rollback / Activate — precisely what each does

- **Publish** (`services.publish_theme`): the theme's current DRAFT `ThemeVersion` is validated, marked `PUBLISHED` (immutable from this point on), and — in the same transaction — becomes both that `Theme`'s `active_version` **and** the site's sole active `Theme` (deactivating whichever theme was previously active). Publish and "go live" are one action; see the Phase 02 plan's judgment call #2 for why.
- **Rollback** (`services.rollback_theme`): repoints `active_version` to an *older already-published* version of the **same** theme. No new version is created — published rows are immutable, so rollback is purely a pointer change, and the version being rolled back *from* is left untouched (still published, still available to roll forward to again).
- **Activate** (`services.activate_theme`): switches which *entire Theme* is the site's active one, without publishing anything — for when there's more than one Theme (e.g. a duplicated seasonal theme) and you want to switch back to a previously-published one.

All three, plus `create_theme`/`update_draft_tokens`/`duplicate_theme`/`delete_theme`, call `apps.audit.services.record()` inside the same transaction — see [theme-security.md](theme-security.md) for the audit mapping table.

## 8. Appearance resolution (light/dark/system) — no flash, no JS required for it

Precedence, exactly:
1. **Authenticated user with an explicit `light`/`dark` preference** — resolved server-side by `apps/theme/context_processors.py:appearance()`, rendered directly as `<html data-theme="light|dark">` in the initial response. Nothing to flash: the correct attribute is present before a single byte of CSS/JS loads.
2. **Anonymous, or preference is `system`/unset** — `data-theme` is omitted entirely, and the `@media (prefers-color-scheme: dark)` rule already in `app.css` (Phase 01) takes over natively in the browser, zero JavaScript involved.

The navbar's appearance switcher (`static/src/js/components/appearance.js`) is the one place real JS matters: clicking Light/Dark/System sets `document.documentElement.dataset.theme` *immediately* (optimistic UI, no waiting on a round trip) and fires a background `fetch()` POST to `/preferences/appearance/` to persist it — deliberately plain `fetch`, not htmx, since there's no HTML to swap, only a value to save.

## 9. Theme Studio's live preview — genuinely zero DB writes per keystroke

Every token field in `ThemeStudioForm` carries a `data-preview-*` attribute (`data-preview-color`, `data-preview-mode`, `data-preview-radius`, `data-preview-typography`) set in `forms.py`. `static/src/js/components/theme-studio.js` listens for `input` events on the whole form (event delegation — one listener, not one per field) and, for each change, calls `preview.style.setProperty(cssVarName, value)` on the preview pane element **only** — never on `:root`. This means:
- Nothing is saved to Postgres until "Save draft" is actually submitted.
- The rest of the admin's own UI (navbar, sidebar) stays on the *real* active theme the whole time — only the scoped preview pane reflects the unsaved edit, because CSS custom properties inherit downward from whichever element they're set on.
- The preview pane's own light/dark toggle just changes which token suffix (`_light`/`_dark`) the same listener applies — no server round-trip for that either.

The preview pane's content (`templates/theme/partials/preview_sample.html`) is the exact same partial reused on `/settings/themes/styleguide/`, so Theme Studio's preview is never a fake mockup.
