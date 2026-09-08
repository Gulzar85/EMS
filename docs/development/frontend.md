# Frontend (Phase 01)

See [docs/architecture/frontend-architecture.md](../architecture/frontend-architecture.md)
and [docs/architecture/theme-architecture.md](../architecture/theme-architecture.md)
for the Phase 00 rationale. This page is the Phase 01 implementation
reference.

## Build pipeline

Node is used for exactly one thing: compiling Tailwind CSS. There is no
JS bundler — Alpine.js and htmx are vendored, pinned, single-file builds.

```
static/
├── src/
│   ├── css/app.css     # Tailwind v4 entry point — the only file you edit
│   └── js/              # app.js, alpine/index.js, htmx/index.js — hand-written
├── vendor/js/            # alpine.min.js, htmx.min.js — pinned versions, do not edit
└── dist/                 # BUILD OUTPUT ONLY — never edit, never commit real content
```

```bash
npm install        # once
npm run build      # tailwind + copy JS into static/dist/
npm run watch:css   # tailwind in watch mode while developing
```

`static/dist/` is what `STATICFILES_DIRS` points to — Django never serves
`static/src/` or `static/vendor/` directly.

## Design tokens (Tailwind v4 `@theme`)

Colors are declared as CSS custom properties in `static/src/css/app.css`
and Tailwind generates real utility classes from them that reference the
variable at runtime (`text-primary` compiles to `color: var(--color-primary)`,
not an inlined hex value) — that's what makes Phase 02's Dynamic Theme
Engine possible without touching Tailwind's build.

**Naming note (a real conflict found during Phase 01, resolved deliberately):**
Tailwind auto-generates `bg-`/`text-`/`border-` utilities from every
`--color-{name}` variable. Phase 00's "Primary"/"Secondary" (brand/action
colors) and "Text primary"/"Text secondary" (default text colors) can't
both claim the word "primary." Since Phase 01 section 50 explicitly wants
`text-primary` and `border-default` as literal class names, those win the
short names; the brand/action palette is namespaced under `--color-brand-*`
instead. See the comment block at the top of `app.css` for the full
mapping.

| Utility | CSS variable | Meaning |
|---|---|---|
| `bg-brand`, `bg-brand-hover` | `--color-brand`, `--color-brand-hover` | Primary action color (Phase 00's "Primary") |
| `bg-background` | `--color-background` | Page background |
| `bg-surface` | `--color-surface` | Card/panel surfaces |
| `text-primary` | `--color-primary` | Default text |
| `text-secondary` | `--color-secondary` | Muted/secondary text |
| `border-default` | `--color-default` | Default border |
| `bg-success`/`bg-warning`/`bg-danger`/`bg-info` | `--color-success` etc. | Status colors |

Components must only ever use these semantic utilities — never a raw
palette class like `bg-red-600` — so Phase 02 can restyle the whole app by
changing variable values alone.

## Components (django-cotton)

`COTTON_DIR = "components"` (see `config/settings/base.py`), so
`<c-button>` resolves to `templates/components/button.html`, matching the
Phase 00 template tree exactly (not django-cotton's own `cotton/` default).

Available now: `<c-button>` (supports `variant`, `type`, `href` — passing
`href` renders an `<a>` instead of a `<button>`), `<c-card>` (supports
`title`), `<c-badge>` (supports `variant`). Any other HTML attribute you
pass through (`hx-get`, `id`, `aria-*`, ...) is spread onto the root
element automatically via django-cotton's `{{ attrs }}`.

**Known django-cotton quirk (found during Phase 01):** a Django `{# ... #}`
comment spanning multiple lines, placed in a template that also uses
`<c-...>` tags, is not stripped correctly by django-cotton's regex-based
compiler — it leaks into the rendered HTML as literal text. A *single-line*
`{# ... #}` comment is fine. Prefer plain Python/HTML comments over
multi-line template comments in any template that uses cotton components.

## Icons

Lucide SVGs, ISC licensed, vendored (not an npm/runtime dependency) under
`apps/core/static/core/icons/`. Rendered via `{% load icons %}{% icon "name" size=20 class_name="..." %}`
(`class_name`, not `class` — a reserved Python keyword). To add an icon:
download the raw SVG for the name you want from lucide.dev (or extract it
from the `lucide-static` npm package) and drop it into that folder — no
other wiring needed.

## Alpine.js / htmx conventions

- Alpine is strictly client-side UI state (dropdowns, the responsive
  sidebar) — never a source of truth for server data.
- Load order in `base/blank.html` matters: htmx vendor → `htmx/index.js` →
  `alpine/index.js` (registers components on `alpine:init`) → `app.js` →
  vendored `alpine.min.js` **with `defer`** (Alpine's documented init order
  — it must run last).
- `htmx/index.js` attaches the CSRF token from Django's `csrftoken` cookie
  to every htmx request, toggles a page-level loading class, and pushes
  errors into a shared Alpine `toast` store (rendered by
  `templates/partials/_toasts.html`).
- Newly-swapped htmx content is re-scanned by Alpine automatically via an
  `htmx:afterSettle` → `Alpine.initTree()` listener.
