# Design System

Status: **Implemented (Phase 02)**
Audience: Engineers and designers implementing UI for the EMS.

Related documents:
- [Frontend Architecture](../architecture/frontend-architecture.md)
- [Theme Architecture](../architecture/theme-architecture.md)
- [Theme System — implementation mechanics](theme-system.md)
- [Component Architecture](components.md)

This document describes the **design tokens** and **visual language** of the EMS as actually implemented. All values below are the seeded defaults (`apps/theme/migrations/0002_seed_default_theme.py`) and are runtime-configurable through Theme Studio — nothing here is hardcoded in templates as a literal value; components use the semantic utility classes only.

---

## 1. Design tokens reference

### 1.1 Color roles

| Role | Utility class | CSS variable | Theme Studio field(s) | Notes |
|---|---|---|---|---|
| Brand / primary action | `bg-brand`, `text-brand` | `--color-brand` | `color_brand_light` / `_dark` | Primary buttons, active nav item, focus rings |
| Brand hover | `bg-brand-hover` | `--color-brand-hover` | `color_brand_hover_*` | Button `:hover` |
| Brand secondary | `bg-brand-secondary` | `--color-brand-secondary` | `color_brand_secondary_*` | Secondary brand accent |
| Brand accent | `bg-brand-accent` | `--color-brand-accent` | `color_brand_accent_*` | Decorative accents |
| Background | `bg-background` | `--color-background` | `color_background_*` | `<body>` background |
| Surface | `bg-surface` | `--color-surface` | `color_surface_*` | Cards, modals, tables, dropdowns |
| Default text | `text-primary` | `--color-primary` | `color_text_primary_*` | Main body/heading text |
| Secondary text | `text-secondary` | `--color-secondary` | `color_text_secondary_*` | Helper text, timestamps, metadata |
| Default border | `border-default` | `--color-default` | `color_border_default_*` | Table dividers, input/card borders |
| Success | `bg-success`, `text-success` | `--color-success` | `color_success_*` | Success alerts, "Active" badges |
| Warning | `bg-warning`, `text-warning` | `--color-warning` | `color_warning_*` | Pending states, expiring items |
| Danger | `bg-danger`, `text-danger` | `--color-danger` | `color_danger_*` | Destructive actions, validation errors |
| Info | `bg-info`, `text-info` | `--color-info` | `color_info_*` | Informational alerts, "Draft" badges |

**Naming note** (a real conflict found while implementing, not a design choice made lightly): Tailwind v4 auto-generates `bg-`/`text-`/`border-` utilities from every `--color-{name}` theme variable. "Primary" (a brand color, Phase 00's term) and "Text primary" (default text color) can't both claim the word "primary" as a class name. `text-primary`/`border-default` were given the short names because Phase 01's own spec asked for them literally; the brand palette lives under `--color-brand-*` instead. Full explanation: the comment block at the top of `static/src/css/app.css`.

Every color role stores **both** a `light` and a `dark` hex value in the same `ThemeVersion.tokens` entry — see [theme-system.md](theme-system.md) §3.

### 1.2 Typography

| Token | CSS variable | Theme Studio field | Notes |
|---|---|---|---|
| Font family | `--font-sans` | `font_family` | Applied via Tailwind's `font-sans` (the default `font-family` for the whole app) |
| Base font size | `--font-size-base` | `font_size_base` | `16px` default |

Only these two are currently theme-editable. A heading scale / weight scale is not implemented — headings use Tailwind's static `text-lg font-semibold` etc. utility classes directly, not a derived token, since no product requirement has asked for a configurable type scale yet (see [theme-development.md](../development/theme-development.md) on adding one).

### 1.3 Radius

| Token | CSS variable | Theme Studio field | Used by |
|---|---|---|---|
| Small | `--radius-sm` | `radius_sm` | Badges, small inline elements |
| Medium | `--radius-md` | `radius_md` | — |
| Large | `--radius-lg` | `radius_lg` | — |

Separately, three **static** (not theme-editable) radius tokens exist in `app.css` for structural component shapes: `--radius-button`, `--radius-card`, `--radius-input`. These are deliberately not in the token schema — they're a code-level design decision (how rounded a button *shape* is), not a brand color/typography knob an admin adjusts. Promoting them into the schema is possible later if a real need appears (see [theme-development.md](../development/theme-development.md)).

### 1.4 Layout (static, not theme-editable)

`--sidebar-width-expanded`, `--sidebar-width-collapsed`, `--navbar-height` are fixed in `app.css`. No product requirement has asked for these to be admin-configurable; they stay static until one does.

---

## 2. Light / Dark / System — precisely how resolution works

1. Every color token stores a `light` and `dark` hex value.
2. `render_theme_css()` ([theme-system.md](theme-system.md) §4) emits three CSS blocks: a base `:root` (light values), `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { ... } }` (dark values, applies automatically under OS dark mode), and `:root[data-theme="dark"] { ... }` (dark values, applies whenever `data-theme="dark"` is explicitly set, regardless of OS preference).
3. **Resolution precedence**, server-side, no JavaScript required for it:
   1. An authenticated user's explicit `light`/`dark` `UserThemePreference` — rendered directly as `<html data-theme="...">` by `apps/theme/context_processors.py:appearance()`, present before any byte of the response body.
   2. Anonymous user, or preference is `system`/unset — `data-theme` is omitted; the browser's own `prefers-color-scheme` media query resolves it natively.
4. The navbar's appearance switcher is the only place JS is involved: it sets `document.documentElement.dataset.theme` immediately for instant feedback, then persists the choice via a background `fetch()` POST (see [theme-system.md](theme-system.md) §8).

---

## 3. Visual language principles

EMS is used by HR, Operations, Area/Regional Management, Finance/Payroll, Training, and employees, frequently against large datasets. The visual language prioritizes clarity and scan-ability over decoration.

### Accessible contrast

Target: WCAG 2.1 AA (4.5:1 normal text, 3:1 large text/UI). Stated as a **goal pending brand sign-off** — the seeded default colors are placeholders (see `apps/theme/migrations/0002_seed_default_theme.py`), and AA compliance needs re-verification once real McDonald's Pakistan brand values are entered into Theme Studio. No automated contrast checker is built into Theme Studio yet (a documented gap, not a silent omission — see Known Issues in the Phase 02 report).

Semantic colors (success/warning/danger/info) are never the only signal — badges/alerts always carry an icon or text label too.

### Consistent iconography

Lucide icons only, vendored as static SVGs (`apps/core/static/core/icons/`, see [Component Architecture](components.md)), rendered inline so they inherit `currentColor` and pick up theme colors automatically. No other icon set is mixed in.

### Enterprise tone

Flat surfaces, minimal shadows, functional-only motion (dropdown/modal transitions, htmx swap states) — no decorative animation.

### Density

Not implemented as a configurable token in Phase 02 (no `--spacing-unit`/compact-mode toggle exists yet). Tailwind's standard spacing utilities are used directly in component templates. A future compact-mode token, if needed, would follow the same pattern as radius: add it to the schema, add a CSS variable, add a Theme Studio field.
