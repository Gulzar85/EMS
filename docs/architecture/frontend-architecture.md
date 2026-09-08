# Frontend Architecture

Status: Final (Phase 01 baseline)
Audience: Engineers implementing the Django-based Employee Management System (EMS) for McDonald's Pakistan

Related documents:
- [ADR-004: Server-Rendered UI (No SPA)](../adr/ADR-004-server-rendered-ui.md)
- [ADR-005: HTMX + Alpine.js for Interactivity](../adr/ADR-005-htmx-alpine.md)
- [Theme Architecture](theme-architecture.md)
- [Design System](../frontend/design-system.md)
- [Component Architecture](../frontend/component-architecture.md)
- [Theme System (implementation mechanics)](../frontend/theme-system.md)

---

## 1. Stack Overview and Rationale

The EMS frontend is **server-rendered Django** (Django templates) enhanced with a small set of focused libraries. There is no SPA framework and no client-side build-time application state.

| Layer | Choice | Purpose |
|---|---|---|
| Markup | HTML5 (Django templates) | Structure, rendered server-side |
| Styling | Tailwind CSS (JIT, CLI build) | Utility-first styling, themeable via CSS variables |
| Interactivity (local) | Alpine.js | Small, declarative client-side UI state |
| Interactivity (server round-trip) | HTMX | Partial page updates without full reloads or a JSON API layer |
| Icons | Lucide Icons | Consistent, tree-shakeable icon set |
| Forms | django-crispy-forms + crispy-tailwind | Server-validated forms rendered with themed Tailwind markup |
| Components | django-cotton (structural) / `{% include %}` + template tags (simple) | Reusable template components |
| Tabular data | django-tables2 + django-filter | Sortable, paginated, filterable employee lists |
| Bulk data | django-import-export | Excel import/export — directly replaces the manual Excel workflows EMS displaces |
| Dates | Flatpickr | Lightweight date pickers for effective-dated HR records |
| Searchable selects | Tom Select | Large restaurant/employee/manager pickers |
| Charts | Chart.js | Dashboard bar/line/pie charts |

### Why no SPA (React/Vue/etc.)

EMS is a data-entry- and record-heavy enterprise HR system, not a real-time collaborative or highly stateful client application. There is no demonstrated requirement for client-side routing, offline support, or complex client state machines. A SPA would require:

- A separate JSON API layer duplicating validation and authorization logic already required server-side in Django.
- A JS build toolchain (bundler, transpiler, state management library) with its own dependency and security surface.
- Two sources of truth for business rules (server + client), which directly conflicts with the project's core principle that **business logic never lives in the client**.

Server-rendered HTML + HTMX gives the same perceived interactivity (partial updates, inline edits, modals, search-as-you-type) while keeping Django views/services/selectors as the single source of truth. See [ADR-004](../adr/ADR-004-server-rendered-ui.md) for the full trade-off analysis and [ADR-005](../adr/ADR-005-htmx-alpine.md) for why HTMX + Alpine specifically (over Turbo/Stimulus/Livewire-style alternatives).

### Why no jQuery

Alpine.js and HTMX's `hx-*` attributes cover all the DOM manipulation and AJAX use cases jQuery historically served, with a fraction of the payload and no imperative spaghetti. Tom Select, Flatpickr, and Chart.js are all jQuery-free by design, keeping the dependency graph minimal.

---

## 2. Template Architecture

Templates are organized by **role**, not just by app, so it is always clear whether a file is a shell, a reusable piece, an HTMX fragment, or a full page.

```
templates/
├── base/
│   ├── base.html                 # Full HTML document shell: <head>, theme.css link, global scripts
│   └── htmx-base.html            # Minimal shell for partial-only / HX-Request responses (no <head>)
├── layouts/
│   ├── app-shell.html            # Authenticated shell: sidebar + navbar + content slot
│   └── auth-layout.html          # Centered layout for login/password-reset/first-run screens
├── components/
│   ├── button.html                # or <c-button> via django-cotton
│   ├── card.html                  # <c-card> with header/body/footer slots
│   ├── modal.html                 # <c-modal>
│   ├── data_table.html            # <c-data-table> wrapping django-tables2 output
│   ├── badge.html
│   └── ... (full inventory: see component-architecture.md)
├── partials/
│   ├── _employee_row.html         # Single <tr>, returned on inline edit / HTMX row refresh
│   ├── _employee_table.html       # Table body fragment for search-as-you-type / pagination
│   └── _stat_card_headcount.html  # Dashboard stat card fragment, refreshed via HX-Trigger
└── pages/
    ├── employees/
    │   ├── list.html               # Extends app-shell.html, includes _employee_table.html
    │   └── detail.html
    ├── payroll/
    │   └── run_detail.html
    └── dashboard/
        └── index.html
```

### `templates/base/`
The two root shells. `base.html` is used for any full-page GET request (first load, hard refresh, direct navigation). `htmx-base.html` is a stripped-down shell (no `<head>`, no global nav) that page templates can extend when a view must serve **both** a full page and an HTMX fragment from the same template using `{% if request.htmx %}...{% endif %}`-style conditionals, or more commonly, views pick between a full `pages/...html` template and a `partials/_....html` template depending on the `HX-Request` header (see §4).

### `templates/layouts/`
Structural shells shared across many pages within a section of the app. `app-shell.html` renders the sidebar, navbar, breadcrumb slot, and a `{% block content %}` for the authenticated area (HR, Operations, Finance, etc.). `auth-layout.html` is used for login and other unauthenticated screens.

### `templates/components/`
The reusable component inventory (Buttons, Cards, Stat Cards, Tables, Modals, Badges, etc. — full list and implementation notes in [component-architecture.md](../frontend/component-architecture.md)). These are the **only** place Tailwind's theme-variable utility classes (e.g. `bg-[var(--color-primary)]`) are written for a given component, so a visual change to "how all buttons look" happens in one file.

### `templates/partials/`
HTMX fragment templates — never rendered as a full page, always returned as the body of an `HX-Request` response. Named with a leading underscore by convention (`_employee_row.html`) to visually distinguish them from full page templates in editors and directory listings.

### `templates/pages/<app>/`
One directory per domain app (`employees`, `payroll`, `training`, `restaurants`, `dashboard`, ...), mirroring the Django app structure. Page templates extend `layouts/app-shell.html` and compose `components/` and `partials/` fragments.

---

## 3. Static File Architecture and Tailwind Build Pipeline

```
static/
├── src/
│   ├── css/
│   │   ├── input.css              # @tailwind base/components/utilities + custom layer
│   │   └── components.css         # Hand-written @layer components (rare — prefer utility classes in templates)
│   └── js/
│       ├── alpine/
│       │   ├── dropdown.js        # Reusable Alpine.data() component definitions
│       │   ├── modal.js
│       │   └── wizard.js
│       └── app.js                 # Entry point: imports Alpine, htmx, Lucide init, Alpine.data() registrations
└── dist/                          # Gitignored. Build output only.
    ├── css/app.css                 # Tailwind CLI output (minified)
    └── js/app.js                   # Bundled/minified JS (esbuild or similar, if needed)
```

### Build pipeline

1. **Source of truth for classes**: Tailwind's JIT engine scans `templates/**/*.html` (and, if ever introduced, any `.py` files using template-string class names — a pattern this project avoids specifically so the scan surface stays limited to templates) for class name occurrences.
2. **Build command**, run in CI/deploy (not at request time):
   ```bash
   npx tailwindcss -i static/src/css/input.css -o static/dist/css/app.css --minify
   ```
3. **Output**: a single minified `static/dist/css/app.css` containing only the utility classes actually referenced anywhere in the template tree — no dead CSS, no unbounded growth, regardless of how many theme variables exist (because the *value* of a variable is a runtime concern; the *existence* of the utility class `bg-[var(--color-primary)]` is a build-time concern — see [theme-architecture.md](theme-architecture.md) for the full explanation of this split).
4. **Collection**: Django's `collectstatic` picks up `static/dist/**` (and any other app static files) into `STATIC_ROOT` for serving (via whitenoise or the web server) in each environment.
5. `static/dist/` is gitignored — it is a build artifact, regenerated on every deploy, never hand-edited or committed.

No `django-compressor` step is used for CSS: the Tailwind CLI build **is** the compression/bundling step. `django-compressor` is unnecessary complexity on top of a pipeline that already produces one static, minified file.

---

## 4. HTMX Conventions

HTMX is the default mechanism for any interaction that needs new data from the server without a full page navigation: search-as-you-type tables, inline edit, on-demand modals, infinite scroll/pagination, and refreshing one part of the page after an action elsewhere on the page.

### 4.1 Partial vs full response pattern

Every Django view that can be reached both by direct navigation and by an HTMX request checks the `HX-Request` header and returns the appropriate template:

```python
def employee_list(request):
    employees = filter_employees(request)  # selector/service, not template logic
    context = {"employees": employees}
    if request.headers.get("HX-Request") == "true":
        return render(request, "partials/_employee_table.html", context)
    return render(request, "pages/employees/list.html", context)
```

Convention: a small `request.htmx` boolean (via `django-htmx`, a required dependency for this convention) is used instead of manually reading headers, e.g. `if request.htmx: ...`.

### 4.2 `HX-Trigger` for cross-component events

When an action in one part of the page must refresh an unrelated component elsewhere on the page (e.g. submitting a "Add Employee" form should refresh a headcount stat card in the dashboard header), the view sets the `HX-Trigger` response header to fire a custom DOM event:

```python
response = render(request, "partials/_employee_row.html", context)
response["HX-Trigger"] = "employeeCreated"
return response
```

The stat card fragment listens for that event and re-fetches itself:

```html
<div id="stat-headcount"
     hx-get="{% url 'dashboard:stat_headcount' %}"
     hx-trigger="load, employeeCreated from:body">
</div>
```

This keeps components decoupled — the form that creates an employee does not need to know the stat card exists; it only announces that something happened.

### 4.3 Out-of-band swaps

When a single response must update **multiple, non-adjacent** regions of the page (e.g. the main table row *and* a summary count *and* a toast notification), the partial template includes additional elements marked `hx-swap-oob="true"` alongside the primary response fragment:

```html
{% comment %} Primary response: the updated row {% endcomment %}
<tr id="employee-row-{{ employee.id }}">...</tr>

{% comment %} Out-of-band: update the count without a separate round-trip {% endcomment %}
<span id="employee-count" hx-swap-oob="true">{{ total_count }}</span>

{% comment %} Out-of-band: show a toast {% endcomment %}
<div id="toast-region" hx-swap-oob="true">
  {% include "components/alert.html" with variant="success" message="Employee updated." %}
</div>
```

Out-of-band swaps are preferred over `HX-Trigger` + a second round-trip whenever the updated content is already known at response time (cheap to include inline); `HX-Trigger` is preferred when the listening component needs to independently re-fetch its own state (e.g. a count that depends on more than just this one action).

### 4.4 Loading indicators

Every HTMX-triggered element that can take a perceptible amount of time specifies `hx-indicator` pointing at a scoped loading element (spinner, skeleton row, or button-disabled state), rather than relying on a single global spinner:

```html
<button hx-post="{% url 'employees:save' employee.id %}"
        hx-indicator="#save-spinner">
  Save
</button>
<span id="save-spinner" class="htmx-indicator">
  {% include "components/loading_state.html" %}
</span>
```

HTMX toggles the `htmx-request` class on the indicator automatically; the component's CSS (via the themed `loading_state` component) handles show/hide.

### 4.5 Error handling

HTMX response codes map to a consistent UI pattern:

| Response | Handling |
|---|---|
| `200` with form errors (validation failure) | View re-renders the **form partial** with `form.errors` populated, HTTP status `422` (Unprocessable Entity, HTMX still swaps content on non-2xx by configuration — see below). Errors surface inline via crispy-tailwind field error styling. |
| `4xx` (e.g. `403` permission denied, `404`) | A global `htmx:responseError` listener (registered once in `app.js`) shows a toast/alert component with a generic message; the swap target is left unchanged. |
| `5xx` | Same global listener shows a "Something went wrong" alert (Error State component) and logs the event; no partial content is trusted from a 500 response. |
| Network failure (`htmx:sendError`) | Same global listener, offline-specific message. |

Django is configured (`htmx.config.responseHandling` client-side, or simply returning `200`/`422` consistently from views) so that **validation errors always come back as a `200`/`422` with a real form partial to swap in**, and only genuine server/permission failures produce the generic toast path — this keeps "please fix this field" from ever looking like a system error.

---

## 5. Alpine.js Conventions

Alpine.js is used **only** for client-side UI state that has no server-side meaning: whether a dropdown is open, which tab is active, whether a modal is visible, which step of a multi-step form wizard is currently displayed. Alpine never holds a copy of server data that could go stale, and it never re-implements a validation or business rule that also exists in a Django form/service — if a rule matters, it is enforced server-side and Alpine only reflects UI state around it.

### Decision rule: Alpine local state vs server round-trip

| Situation | Use |
|---|---|
| Toggle visibility of a menu/modal/accordion | Alpine `x-data` |
| Switch visible tab panel (no new data needed) | Alpine `x-data` |
| Track which step of a wizard is shown (fields already in the DOM) | Alpine `x-data` |
| Filter/search a list against the database | HTMX (`hx-get` to a view) |
| Submit a form, get validation results | HTMX (`hx-post`, swap form partial) |
| Show a count/aggregate that depends on current DB state | HTMX (fetched or refreshed via `HX-Trigger`) |

### Standard Alpine patterns (registered as `Alpine.data()` components in `static/src/js/alpine/`)

- **Dropdown** (`dropdown.js`): `x-data="dropdown()"`, exposes `open`, `toggle()`, closes on outside click (`@click.outside`) and `Escape`.
- **Modal** (`modal.js`): `x-data="modal()"`, exposes `open`/`close`; modal *content* for on-demand modals is still loaded via `hx-get` into the modal body — Alpine only controls the show/hide chrome.
- **Tabs** (`tabs.js`): `x-data="tabs('general')"`, tracks `activeTab`, toggles `x-show`/`aria-selected` on panels already present in the DOM.
- **Wizard** (`wizard.js`): `x-data="wizard(totalSteps)"`, tracks `currentStep`, `next()`/`back()`; the **final submit** of a multi-step form is a normal (or HTMX) POST validated entirely server-side — Alpine's step tracking is purely presentational and does not decide whether data is valid.

Alpine components are kept small and named consistently (`dropdown()`, `modal()`, `tabs(initial)`, `wizard(steps)`) so any template can reuse them via `x-data="dropdown()"` without redefining behavior inline. One-off, trivial state (e.g. a single "show password" toggle) may use inline `x-data="{ show: false }"` rather than a registered component.

---

## 6. Form Architecture

1. **Definition**: Django `forms.Form` / `forms.ModelForm` subclasses own all field definitions, widgets, and validation (`clean_*`, `clean()`), per the project's principle that business rules live server-side.
2. **Rendering**: Forms are rendered with `{% crispy form %}` using a **custom crispy-tailwind pack** that emits the same fixed, theme-variable-referencing utility classes used by the rest of the component inventory (e.g. inputs use `border-[var(--color-border)] rounded-[var(--radius-input)]`), so every form automatically matches the active theme with zero per-form styling code.
3. **Validation errors**: When `form.is_valid()` is `False`, the view re-renders the **same form partial** (not the full page) with the bound form (including `form.errors`); crispy-tailwind's field-level error rendering shows inline messages under each invalid field using the `danger` color token, and a summary alert (Alert component) can optionally be rendered above the form for forms with many fields.
4. **HTMX-submitted forms**: Forms that submit via `hx-post` target their own container (`hx-target="this"` or a wrapping `<div id="employee-form">`) and use `hx-swap="outerHTML"`, so a failed validation response simply replaces the form with itself plus errors — no page reload, scroll position preserved, and the same Django form/view code path handles both the HTMX and non-JS-fallback (full page POST) cases identically.
5. **Non-JS fallback**: Because HTMX progressively enhances a normal `<form method="post">`, every form remains a fully working standard POST if JavaScript is unavailable — the `hx-*` attributes are additive, not a replacement mechanism.

---

## 7. Summary of Boundaries

- **Django views/services/selectors**: own business logic, validation, authorization, and what data exists.
- **Django templates**: render state that was already computed server-side; no business logic in template tags/filters beyond presentation formatting.
- **Alpine.js**: owns transient client-only UI state; never a source of truth for server data.
- **HTMX**: the transport for getting updated server-rendered HTML into the page without a full navigation.
- **Tailwind**: owns visual styling, entirely through a fixed set of utility classes that reference runtime CSS variables (see [theme-architecture.md](theme-architecture.md)).
