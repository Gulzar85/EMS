# Alpine.js

Status: **Implemented**. Alpine.js 3.17.2 + the official `@alpinejs/focus` plugin, both vendored as single pinned files (`static/vendor/js/alpine.min.js`, `alpine-focus.min.js`) — not npm runtime dependencies.

Related: [Frontend Architecture](../architecture/frontend-architecture.md), [HTMX](htmx.md), [Component Inventory](components.md).

## The one hard rule

Alpine is client-side UI state only. It never becomes the source of truth for server data, never implements a business rule that also exists server-side, and never touches persistence directly except through a real HTTP call to a real Django view (which re-validates everything — see [Theme Studio's live preview](theme-system.md) §9 and [the appearance switcher](theme-system.md) §8 for the two places this project's JS actually talks to the server).

## Load order (this matters — get it wrong and components silently don't register)

```html
<script src="{% static 'js/vendor/htmx.min.js' %}"></script>
<script src="{% static 'js/htmx/index.js' %}"></script>
<script src="{% static 'js/alpine/index.js' %}"></script>       <!-- registers components -->
<script src="{% static 'js/app.js' %}"></script>
<script src="{% static 'js/vendor/alpine-focus.min.js' %}" defer></script>  <!-- plugin, before core -->
<script src="{% static 'js/vendor/alpine.min.js' %}" defer></script>        <!-- core, must be last -->
```

Alpine's own documented rule: plugins load before core, core loads last with `defer`. Component registration (`Alpine.data(...)`) happens on the `alpine:init` event, which core fires just before it scans the DOM — registering it in a plain (non-deferred) script tag earlier in the document guarantees it's attached before that event fires.

## Registered components (`static/src/js/alpine/index.js` + `static/src/js/components/`)

| Component | Purpose |
|---|---|
| `appShell` | Sidebar expanded/collapsed (desktop) and mobile drawer open/closed — no persistence, resets on reload (Phase 01 decision, unchanged) |
| `dropdown` | Backs `<c-dropdown>` — open state, `@click.outside`, Escape |
| `Alpine.store('toast')` | Shared toast queue; htmx error handlers and any future code push into it via a `toast` window event |
| `themeStudio` | Live preview — see [theme-system.md §9](theme-system.md) |
| `appearanceSwitcher` | Optimistic light/dark/system switching — see [theme-system.md §8](theme-system.md) |

## Why `@alpinejs/focus`

The one plugin added beyond Alpine core, specifically for `<c-modal>`: `x-trap="open_var"` keeps Tab navigation inside an open modal and restores focus to the trigger on close — a real accessibility requirement (Phase 02 plan §38), not achievable with core Alpine directives alone without hand-rolling a focus trap.

## `x-teleport`

Used by `<c-modal>` (`x-teleport="body"`) — a core Alpine directive (no plugin needed), moves the modal's DOM node to the end of `<body>` at runtime so it isn't clipped by an `overflow:hidden` ancestor, while preserving its original reactive scope (a modal opened from deep inside a form still sees that form's `x-data`).

## Event delegation over `x-model` where forms are involved

`themeStudio`'s live preview listens for `input` events on the whole form container rather than wiring `x-model` onto every field individually — because those fields are real Django form inputs rendered by crispy-forms, not hand-written Alpine templates. Each field carries a `data-preview-*` attribute (set in `apps/theme/forms.py`) that the single delegated listener reads. This avoids needing a custom widget just to attach Alpine bindings.
