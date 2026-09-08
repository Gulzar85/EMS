# Testing Strategy

Status: Phase 00 architecture baseline. Defines how the Django-based EMS is tested at each architectural layer described in [Coding Standards](./coding-standards.md).

Related documents:
- [Coding Standards](./coding-standards.md)
- [Git Strategy](./git-strategy.md)
- [Database Conventions](../database/database-conventions.md)

## 1. Tooling

| Tool | Role |
|---|---|
| **pytest** + **pytest-django** | Primary test runner |
| **factory_boy** | Test data factories (Recommended) |
| **Playwright** | Browser-driven end-to-end tests (Recommended, used sparingly) |

### Why pytest-django over Django's built-in `TestCase`

Django's built-in `django.test.TestCase` runner works, but **pytest-django** is chosen instead for the ergonomics that matter at this project's scale:

- **Fixtures** compose more naturally than `setUp`/`setUpClass` inheritance chains — a `restaurant_manager_user` fixture, an `employee` fixture, and a `leave_balance` fixture can be mixed and matched per test without building a deep base-`TestCase` hierarchy.
- **Parametrization** (`@pytest.mark.parametrize`) makes it cheap to run the same test across multiple scope levels (GLOBAL/REGION/AREA/RESTAURANT/DEPARTMENT/SELF) or multiple invalid-input cases without copy-pasting test methods.
- Plain `assert` statements instead of `self.assertEqual(...)`-style API, which keeps tests readable.

Under the hood, pytest-django still uses Django's transactional test-database machinery — tests that touch the database are simply marked `@pytest.mark.django_db` (or use the `db` fixture) rather than subclassing `TestCase`. Nothing about the underlying test-database guarantees changes; this is a developer-ergonomics choice, not a different testing model.

### factory_boy (Recommended)

`factory_boy` factories are the natural pairing with pytest fixtures for building valid model instances (an `EmployeeFactory`, `RestaurantFactory`, `UserScopeFactory`) without every test hand-constructing objects field by field. Factories should live alongside the app they belong to (e.g. `apps/employees/tests/factories.py`) and compose across apps via `SubFactory` where a model has cross-app foreign keys (e.g. an `Employee` factory pulling in a `Restaurant` from `organization`).

### Playwright (Recommended, used sparingly)

Playwright is evaluated and recommended for true end-to-end, browser-driven tests of the system's critical **HTMX-driven flows** — the cases where Alpine/HTMX interaction behavior (a partial swap, a modal, an inline edit) can only be verified by actually rendering in a browser and clicking through it. This is deliberately a **small, golden-path suite**, not a UI test framework for exhaustive coverage:

- Example golden path: *create employee → view in list → transfer → verify transfer appears in history.*
- Example golden path: *submit leave request → manager approves → leave balance decrements.*

E2E tests are the most expensive layer to write, run, and maintain (slowest to execute, most brittle to UI changes, hardest to debug on failure), so they earn their place only for flows where a real browser round-trip is the actual risk being tested — not as a substitute for the faster, cheaper layers below.

## 2. What's tested at each layer

### Unit tests
Pure functions with no Django dependency — validators, formatting helpers, date-range overlap math used by services before it ever touches the ORM. Fast, no `django_db` mark needed.

### Model tests
Data-integrity rules enforced at the database layer (see [Coding Standards §4](./coding-standards.md#4-models) and [Database Conventions](../database/database-conventions.md)):

- The effective-dating `ExclusionConstraint` on historical tables (e.g. `EmployeeAssignment`) actually rejects an overlapping `effective_from`/`effective_to` range at the database level — test this by attempting to create the overlapping row directly via the ORM and asserting an `IntegrityError` is raised, independent of whatever the service layer does above it.
- The soft-delete manager excludes inactive/deleted rows from the default queryset, and an explicit "all objects" manager still returns them when needed (e.g. for audit or history views).

### Form tests
- Validation rules on `ModelForm`s used for direct single-model edits (invalid data is rejected, valid data is accepted, error messages are the expected ones).
- crispy-tailwind rendering does not error for each form (a cheap smoke test: `form.helper` renders without raising, catches a broken `Layout` definition immediately rather than at first manual QA).

### Service tests — the bulk of business-logic testing
Since business rules live in `services.py`, this is where test effort concentrates. Using `transfer_employee()` as the running example (see [Coding Standards §7](./coding-standards.md#7-services)):

- A valid transfer **closes the old `EmployeeAssignment`** (`effective_to` set correctly) **and opens a new one**, and both writes happen atomically — if the second write fails, the first is rolled back (test by forcing a failure mid-service and asserting the old assignment is unchanged).
- An overlapping/invalid transfer **raises `OverlappingAssignmentError`** (the domain exception, not a bare `ValidationError` — see [Coding Standards §7](./coding-standards.md#7-services)), and does not partially write.
- A successful transfer **writes an `AuditLog` row** via the `audit` app, with the actor, the old and new state, and a timestamp.
- A caller **without the required scope/permission is denied** — `transfer_employee` called by a user whose `UserScope` doesn't cover the employee's restaurant raises `NotAuthorizedError` and performs no writes at all (policy check happens before any write, per [Coding Standards §7](./coding-standards.md#7-services)).

Every service with a business rule should have both a "happy path" test and at least one test per distinct failure mode (bad input / not authorized / business conflict), since those three are the categories the domain-exception convention exists to distinguish.

### Selector tests
Scope filtering is the thing that actually protects data — so it is tested directly, not just implied by policy tests:

- A Restaurant-Manager-scoped call to `get_employees_for_user(user, ...)` **never returns another restaurant's employees**, even when the underlying table has rows for many restaurants. Construct employees across two+ restaurants, call the selector as a manager scoped to one, and assert the result set contains only that restaurant's employees.
- A GLOBAL-scoped call returns everything; a SELF-scoped call (e.g. an employee viewing their own record) returns exactly one row.
- Selectors return QuerySets — a selector test may also assert the result is still filterable/orderable (i.e. it wasn't accidentally coerced to a list somewhere in the selector).

### Permission / policy tests
The canonical case for this system: **a Restaurant Manager can see an employee's profile but not their compensation.** Test both directions explicitly:

- `can_view_employee(user, employee)` → `True` for a manager scoped to that employee's restaurant.
- `can_view_compensation(user, employee)` → `False` for the same manager, even though they can view the employee record itself.
- Negative cases for every `policies.py` function: a user with no matching `UserScope` at all, a user scoped to a *different* restaurant/region/area, and (where relevant) an inactive/deactivated user.

### HTMX tests
A view that supports both a full-page and a partial response must be tested for both branches: using the Django test client with `HX-Request: true` set in the headers, assert the response renders the **partial** template (e.g. `_employee_row.html`), not the full page template with layout/nav — and the inverse without the header. This is a cheap, high-value test since an HTMX response accidentally rendering a full page (or vice versa) is a common and easy-to-miss regression.

### Integration tests
A full request → service → DB round trip through the Django test client, for the system's critical flows (the same flows that get a golden-path E2E test, but exercised at the HTTP/service layer rather than a real browser) — e.g. `POST /employees/<uuid>/transfer/` as a real request, asserting the DB state and the response, without mocking the service layer.

### End-to-end tests
Playwright, golden paths only, as described in [Tooling](#tooling) above. Not a substitute for the layers above — an E2E failure should be rare and should point at an actual integration/rendering problem, not stand in for missing service or selector test coverage.

## 3. Coverage expectation

No arbitrary blanket coverage percentage is dictated here. Instead:

- **Services, selectors, and policies** — the layers that carry business logic and authorization — should be **close to fully covered**, because that is where the actual risk in this system lives (wrong pay data, wrong scope leakage, wrong approval logic are the failures that matter).
- **Templates and pure CRUD views** (a view that does nothing but call one selector/service and render) need only **smoke coverage** — enough to confirm the page renders and the right template is chosen, not exhaustive branch coverage of Django's own generic view machinery.
- A specific numeric coverage target (e.g. "90% on `services.py`/`selectors.py`") is left as a **team-agreed target to set in Phase 01**, once real apps exist to measure against — inventing a number here would be arbitrary rather than informed by the actual codebase shape.
