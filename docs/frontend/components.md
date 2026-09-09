# Component Inventory

Status: **Implemented (Phase 02)**. Every component listed here is real, in `templates/components/`, and demonstrated on `/settings/themes/styleguide/` (`theme.view_theme` staff users) — that page is the living reference; this document explains the mechanics behind each.

Related: [Frontend Architecture](../architecture/frontend-architecture.md), [Design System](design-system.md), [Alpine.js](alpine.md), [HTMX](htmx.md).

## Conventions

- **File → tag mapping**: `templates/components/empty_state.html` → `<c-empty-state>` (hyphens in the tag, underscores in the filename — django-cotton's own convention).
- **`COTTON_DIR = "components"`** (`config/settings/base.py`) so this maps to `templates/components/`, not cotton's default `templates/cotton/`.
- Every component accepts a `class` cvar that's appended to its root element's class list, so callers can adjust spacing/width without editing the component.
- Extra attributes not declared as a `{% cotton:vars %}` default (e.g. `hx-get`, `@click`, `disabled`, `id`) pass through automatically via cotton's `{{ attrs }}` spread onto the root element.
- **Known gotcha**: a multi-line Django `{# ... #}` comment inside any template that django-cotton compiles is not stripped correctly and leaks into the rendered HTML. Every component file uses single-line comments only. See git history / the note in `apps/theme/tests` for how this was found.

## Inventory

| Component | Variants | Mechanics |
|---|---|---|
| `<c-button>` | `variant`: primary/secondary/danger; `type`; `href` (renders `<a>` instead of `<button>`) | Tailwind classes referencing semantic tokens only |
| `<c-icon-button>` | `variant`: primary/secondary/danger; requires `label` (renders `aria-label`) | Same pattern, square, icon-only |
| `<c-card>` | `title` (optional) | Simple container |
| `<c-badge>` | `variant`: default/brand/success/warning/danger/info | — |
| `<c-alert>` | `variant`: success/warning/danger/info; `dismissible` | Alpine `x-data="{ show: true }"` for the dismiss button |
| `<c-avatar>` | `size`: sm/md/lg; `src` or `initials` | — |
| Inputs/Selects/Textareas/Checkboxes/Radios | — | **Not** cotton components — rendered by crispy-tailwind, themed via a `css_container` override (`apps/core/context_processors.py:crispy_theme`) rather than a second component system. See §"Forms" below. |
| `<c-toggle>` | `model` (an Alpine boolean in scope) | Client-side-only UI state (e.g. a display preference) — real form checkboxes stay on crispy-tailwind |
| `<c-modal>` | `open_var` (an Alpine boolean in scope), `title` | `x-teleport="body"`, focus-trapped via the vendored `@alpinejs/focus` plugin (`x-trap`), Escape/backdrop-dismissible |
| `<c-dropdown>` | `align`: left/right; named slot `trigger` | Generalizes the pattern the navbar's user menu used in Phase 01 — the navbar was refactored onto this component in Phase 02 |
| `<c-tabs>` | `default` | Provides shared `x-data="{ active: ... }"` only — buttons/panels use plain `@click="active = 'x'"` / `x-show="active === 'x'"` directly, more transparent than hiding the wiring behind more templating |
| `<c-breadcrumb>` | — | Caller provides `<li>` items; CSS `::after` renders the `/` separators |
| `<c-pagination>` | `page_obj` (a Django `Page`) | Presentation only over Django's native `Paginator`/`Page` — no custom pagination logic |
| `<c-table>` | — | Wraps caller-provided `<thead>`/`<tbody>` with responsive overflow + consistent cell styling |
| `<c-empty-state>` | `icon`, `title`, `description` | — |
| `<c-loading-state>` | `label` | Spinning `loader-circle` icon |
| `<c-skeleton>` | `class` (size) | Pure CSS `animate-pulse` |
| `<c-tooltip>` | `text`, `position`: top/bottom | Simple, no viewport-collision detection — a deliberate simplification; revisit with a positioning library only if a real case needs it |

## Forms

Django forms (`ThemeCreateForm`, `ThemeStudioForm`, etc.) render via `{% crispy form %}` / `{{ form|crispy }}` (crispy-tailwind), not a parallel cotton form-component system — mixing "five component systems" was an explicit thing to avoid (Phase 02 plan §35). Styling comes from a `css_container` context variable crispy-tailwind looks for (falling back to its own gray palette if absent) — `apps/core/context_processors.py` supplies one built from the same semantic tokens every other component uses (`border-default`, `focus:ring-brand`, `rounded-[var(--radius-input)]`), so no template override was needed, just a context processor.

## Icons

Lucide SVGs (ISC licensed), vendored as individual files under `apps/core/static/core/icons/` — not an npm/runtime dependency. Rendered via `{% load icons %}{% icon "name" size=20 class_name="..." %}` (`apps/core/templatetags/icons.py`). To add one: download the raw SVG for the icon you want from lucide.dev (or `lucide-static`) and drop it in that folder.

## Accessibility notes specific to these components

- `<c-modal>`'s focus trap and `<c-dropdown>`'s `@click.outside`/Escape handling are the two places keyboard/screen-reader correctness mattered most; both were manually verified (Escape closes, Tab stays inside an open modal).
- `<c-icon-button>` requires a `label` prop specifically so an icon-only button can never ship without an accessible name.
- `<c-toggle>` uses `role="switch"` + `aria-checked`, not a bare styled `<div>`.
