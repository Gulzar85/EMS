# Coding Standards

Status: Phase 00 architecture baseline. Applies to the Django-based Employee Management System (EMS) for McDonald's Pakistan. This is a greenfield, documentation-only phase — no code exists yet; these standards govern all code written from Phase 01 onward.

Related documents:
- [Database Conventions](../database/database-conventions.md)
- [Testing Strategy](./testing-strategy.md)
- [Git Strategy](./git-strategy.md)

## 1. Guiding principle

The system is a **modular monolith**: one Django project, many `apps/<domain>` packages (`core`, `accounts`, `organization`, `people`, `employees`, `compensation`, `recruitment`, `onboarding`, `attendance`, `leave`, `performance`, `training`, `documents`, `workflows`, `notifications`, `theme`, `dashboard`, `audit`, `integrations`). Every standard below exists to keep the layering — **thin Views → `services.py` → `selectors.py` → PostgreSQL** — honest as the codebase grows, so that business logic stays testable and authorization stays centrally enforced rather than scattered across templates and views.

## 2. Python

- Target Python 3.12+. Follow PEP 8 as enforced by **Ruff** (see [Tooling](#8-tooling)) rather than by manual review.
- Type hints are **required** on every `services.py` and `selectors.py` function signature (parameters and return type) — these are the modules future maintainers will read to understand system behavior, and hints double as inline documentation of the contract. Type hints are **encouraged but not mandatory** elsewhere (views, forms, admin).
- Prefer explicit, keyword-only arguments for anything beyond one or two positional parameters (see the service naming convention in [Services](#6-services)) — this makes call sites self-documenting and safe to reorder.
- Avoid cleverness: no metaclass magic, no dynamic attribute injection, no monkey-patching. This is an HR system of record; predictable code matters more than terse code.

## 3. Django project structure

### 3.1 Settings

Settings are split, never a single `settings.py`:

```
config/settings/
  base.py    # shared defaults
  dev.py     # local development overrides
  test.py    # CI / pytest overrides
  prod.py    # production overrides
```

All environment-specific values (database credentials, `SECRET_KEY`, Redis URL, Entra ID client secret, feature flags) are read from environment variables via **django-environ**, never hard-coded and never branched on with `if DEBUG:`-style settings logic. `dev.py`, `test.py`, and `prod.py` each `from .base import *` and override only what differs. See [Deployment Architecture](../architecture/deployment-architecture.md) for how these environment variables are supplied per environment.

### 3.2 App structure

Every app under `apps/` follows the same shape, so a developer moving from `attendance` to `leave` finds things in the same place:

```
apps/<app_name>/
  models.py          # or models/ package if the app has several substantial models
  services.py         # writes, business rules, transactions
  selectors.py         # reads, scope-filtered querysets
  policies.py          # can_view_x / can_edit_x authorization functions
  forms.py
  views.py
  urls.py
  admin.py
  tests/
    test_models.py
    test_services.py
    test_selectors.py
    test_policies.py
    test_views.py
```

Not every app needs every file (an app with no HTML screens may have no `forms.py`), but the files that do exist always mean the same thing across apps. When a `models.py` grows unwieldy, convert it to a `models/` package (`models/__init__.py` re-exporting, one file per model or logical model group) — do this before the file becomes unreadable, not after.

## 4. Models

Models are **thin**. A model owns:

- Field definitions, `Meta` (ordering, constraints, indexes — see [Database Conventions](../database/database-conventions.md)).
- Data-integrity validation only, in `clean()` or via model-level `CheckConstraint`/`ExclusionConstraint` — i.e., rules that must hold regardless of *how* a row was written (e.g., "effective_to must be null or after effective_from").
- Simple derived properties (`@property`) that compute from the instance's own fields with no query fan-out.

A model does **not** own business rules that depend on other rows, other apps, or the current user (e.g., "an employee cannot be transferred to a restaurant they're already assigned to on an overlapping date range" belongs in `services.py`, even though the *overlap itself* is also backstopped by a Postgres `ExclusionConstraint` at the database layer — the constraint is the last line of defense, the service is where the business decision and its audit trail live).

Every model that represents a business entity uses the shared `core` app mixins:

- An audit-field mixin (`created_at`, `updated_at`, `created_by`, `updated_by`).
- A soft-delete mixin (`is_active` / `deleted_at`) where the domain calls for soft delete rather than hard delete (most HR records — employees, assignments, documents — are soft-deleted; pure lookup/reference tables may not need it).

## 5. Views

- **Class-based views (CBVs)** are preferred for CRUD-shaped screens (list/detail/create/update/delete of a resource) — they give consistent structure (`get_queryset`, `get_context_data`, `form_valid`) across the whole codebase.
- **Function-based views** are fine, and often clearer, for simple or one-off HTMX endpoints (a single partial re-render, a toggle action) where the CBV machinery would be more ceremony than the view warrants.
- A view calls **at most one service or selector per request/response cycle**. A view that needs data from two selectors composes them explicitly and readably in the view — it does not chain service calls together to build a mini workflow; that composition belongs in a service.
- A view **never performs its own ORM writes**. If a view is calling `.save()`, `.create()`, `.update()`, or `.delete()` directly, that logic has not been factored into a service yet — this is a straightforward review rejection, not a style nitpick, because it's exactly how policy checks and audit logging get silently bypassed.

## 6. Forms

- Use a plain **`ModelForm`** when the form is a direct single-model edit with no business rule attached (e.g., editing a person's phone number). The form saves via its own `save()`.
- Use a **plain `Form`** (not a `ModelForm`) plus an explicit service call in the view for anything with a business rule attached (e.g., "transfer employee" is a form that collects `new_restaurant`, `effective_from`, `reason` and hands them to `transfer_employee(...)`; it does not `save()` anything itself).
- **crispy-tailwind** layout (`FormHelper`, `Layout`, field grouping, column widths) is defined **once, in the form's `__init__`**, not duplicated per-template with `{% crispy %}` tag overrides scattered around. A form's visual layout is part of the form's definition, not the template's.

## 7. Services

- File: one `services.py` per app (or `services/` package if an app's service surface is genuinely large — split by sub-domain, not by CRUD verb).
- Naming: `verb_noun`, e.g. `transfer_employee`, `create_leave_request`, `approve_timesheet`. Keyword-only arguments after the first, e.g.:

  ```python
  def transfer_employee(
      *,
      employee: Employee,
      new_restaurant: Restaurant,
      effective_from: date,
      actor: User,
      reason: str,
  ) -> EmployeeAssignment: ...
  ```

- Services are **plain functions**, not classes, unless the operation is genuinely stateful across multiple calls (rare — most business operations are single atomic transactions and don't need instance state).
- Every service that writes:
  1. Wraps its writes in `transaction.atomic()`.
  2. Checks the relevant `policies.py` function **first**, before touching the database — a denied caller should never see partial side effects.
  3. Raises a **domain exception**, not a bare `django.core.exceptions.ValidationError`, for business-rule violations — e.g. `OverlappingAssignmentError`, `InsufficientLeaveBalanceError`, `NotAuthorizedError`. This lets the calling view distinguish "bad input" (form validation) from "not allowed" (policy denial) from "business conflict" (domain exception) and render the right message/status code for each, instead of collapsing all three into one generic error path.

## 8. Selectors

- File: one `selectors.py` per app.
- Naming: `get_noun_for_user` when the result is scope-sensitive (the common case — almost everything an HR system reads is scoped to who's asking), or plain `get_noun` for genuinely global/unscoped lookups (e.g. a list of countries).
- A scope-sensitive selector always takes `user` as its **first** positional argument, e.g. `get_employees_for_user(user, **filters)`.
- Selectors **return QuerySets, not lists** — never call `list()` or slice inside a selector — so callers can further `.filter()`, order, paginate (via django-tables2/django-filter), or `.count()` without the selector needing to anticipate every downstream need.

## 9. Templates

- Templates contain **no business logic**. A template may format and render; it may not decide. If a `{% if %}` in a template is expressing a business rule rather than a display concern (e.g. "show the salary field only if the viewer is allowed to see it" — as opposed to "show this row only if the list isn't empty"), that decision must already have been made by the view/selector before the template ever sees the data. Authorization is enforced in selectors/services/views — never in templates, and never by simply hiding a field client-side.
- Genuinely reusable formatting (currency display, date formatting per locale, employee status badges) belongs in **template tags/filters**, defined once, not copy-pasted across templates.

## 10. JavaScript / Alpine.js

- Small `x-data` components are **colocated** in a `<script>` block at the bottom of the partial that uses them — keeps the behavior next to the markup it drives, which matters for HTMX-swapped partials that come and go.
- Any Alpine component reused across **3 or more templates** graduates to a shared file under `static/src/js/components/*.js` — duplicating past that point is a maintenance cost, not a convenience.

## 11. HTMX

- Every HTMX-triggering element sets its `hx-target` and `hx-swap` **explicitly**. Relying on HTMX defaults (target = the element itself, swap = `innerHTML`) makes behavior implicit and fragile as templates are refactored — always state the target and swap strategy at the point of use.
- Partial templates that exist only to be swapped in by HTMX are named with a leading underscore (`_employee_row.html`, `_leave_balance_card.html`) so they're visually distinct from full-page templates in a directory listing.
- HTMX endpoints for actions on a resource live **under that resource's own URL path** as POST-only endpoints, not as a separate `/api/`-style URL tree — see [URL architecture](#12-url-architecture) below.

## 12. URL architecture

URLs follow one convention system-wide:

```
/employees/                              # list
/employees/<uuid:public_id>/             # detail
/employees/<uuid:public_id>/edit/        # edit form
/employees/<uuid:public_id>/transfer/    # POST-only action
/organization/
/leave/
/attendance/
/workforce/
/reports/
/settings/
```

- **Plural-noun, app-rooted paths.** Each domain app owns a top-level path segment named for its resource (`/employees/`, `/leave/`, `/attendance/`), included from the project's root `urls.py`.
- **`public_id` (UUID), never the integer PK**, appears in any URL that names a specific record. The auto-incrementing `BigAutoField` primary key is an internal implementation detail; it is never exposed in a URL, never guessable, and never usable to enumerate records. This applies to every user/URL-facing model per the architecture brief: `Employee`, `Person`, `Document`, `LeaveRequest`, and any future model in the same category.
- **Trailing slashes, always** — standard Django convention, backed by `APPEND_SLASH`. No URL pattern omits the trailing slash.
- **Namespacing:** each app's `urls.py` is included under the root `urls.py` with `app_name = "<app_label>"` matching the Django app label exactly, so `{% url "employees:detail" employee.public_id %}` always matches the app it names — no ad hoc namespace aliases.
- **HTMX partial/action endpoints are not a separate URL tree.** An action like "transfer this employee" is `POST /employees/<uuid:public_id>/transfer/`, not `POST /api/employees/transfer/`. A partial re-render is either the same detail/list URL responding differently when it sees the `HX-Request` header (see [Testing Strategy](./testing-strategy.md#htmx-tests)), or a clearly-suffixed sibling path (e.g. `/employees/<uuid:public_id>/summary-card/`) — never a parallel `/api/` namespace, since there is no DRF/API layer in this system yet.

## 13. Database, testing, and Git

These have their own documents and are not duplicated here:

- Schema conventions, indexing, constraints, effective-dating patterns → [Database Conventions](../database/database-conventions.md)
- Test layers, tooling, coverage expectations → [Testing Strategy](./testing-strategy.md)
- Branching, commit conventions, migration review policy → [Git Strategy](./git-strategy.md)

## 14. Documentation / docstrings

Docstrings are required on a `services.py` or `selectors.py` function **only when the WHY isn't already obvious from the function name and signature** — e.g. `transfer_employee(...)` doesn't need a docstring explaining that it transfers an employee, but it may need one line explaining *why* it closes the old assignment with `effective_to = effective_from - 1 day` rather than the same date, if that's a deliberate business decision someone could otherwise "fix" incorrectly. Trivial getters, `__str__`, and boilerplate CBV overrides need no docstring at all. Prefer a good name over a docstring explaining a bad one.

## 15. Tooling

The toolchain is deliberately small:

- **Ruff** — lint *and* format, replacing both `flake8` and `black` with a single fast tool. Ruff's formatter is Black-compatible, so there's no style debate to have.
- **pre-commit** hooks run:
  1. Ruff (lint + format check)
  2. A migration check: `python manage.py makemigrations --check --dry-run` — fails the commit if a model change wasn't accompanied by its migration.
  3. A basic secret scan (e.g. detect-secrets or gitleaks pre-commit hook) — catches accidentally-committed credentials before they leave the developer's machine.
- **pytest** is the test runner (see [Testing Strategy](./testing-strategy.md) for the full testing tool stack).

### Why not more tooling

This list is intentionally not larger, and that's a decision, not an oversight:

- **No separate `isort`/`black`/`flake8`** once Ruff is in place — Ruff replicates all three, and running overlapping tools just means more config files to keep in sync and more chances for two tools to disagree.
- **No mandatory mypy / strict typing** at Phase 00. The type-hint requirement on services/selectors (see [Python](#2-python)) gets most of the documentation value of typing without paying for a full static-typing rollout (django-stubs setup, generic queryset typing, ongoing friction with Django's dynamic bits) before the team has even settled the domain models. **`mypy` + `django-stubs` are noted as Optional/future** — worth revisiting once the core apps stabilize and the team has bandwidth to adopt stricter typing deliberately, not as a Phase 00 mandate.

Additional tooling should clear a real, named bar (an actual recurring bug class it would have caught) before being added — not be adopted speculatively "because other Django projects use it."
