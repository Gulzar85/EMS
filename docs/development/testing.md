# Testing (Phase 01)

Tooling: `pytest` + `pytest-django` (chosen over bare `TestCase` for
fixtures/parametrization ergonomics), `factory_boy` for test data. See
[docs/development/testing-strategy.md](testing-strategy.md) for the full
Phase 00 strategy this implements.

```bash
venv/Scripts/python -m pytest          # everything
venv/Scripts/python -m pytest apps/accounts   # one app
venv/Scripts/python -m pytest -k health       # by keyword
```

Settings: `config/settings/test.py` (fast password hasher, `AXES_ENABLED =
False` so repeated test logins never trip lockout, in-memory email
backend). Configured as `DJANGO_SETTINGS_MODULE` via `pyproject.toml`'s
`[tool.pytest.ini_options]` — no manual flag needed.

## What's covered so far

| Layer | File | What it checks |
|---|---|---|
| Model | `apps/accounts/tests/test_models.py` | Email normalization/uniqueness, password hashing, `create_superuser` flag enforcement, active/inactive authentication |
| Model (abstract) | `apps/core/tests/test_models.py` | `TimeStampedModel`/`PublicIDModel` field contracts (no concrete table exists yet — nothing to round-trip through the DB) |
| View | `tests/test_views.py` | Login-required redirect, login success/failure, logout requires POST, custom 403/404/500 render without a debug traceback |
| Health/HTMX | `tests/test_health.py` | `/health/live/` never touches the DB, `/health/ready/` defaults to JSON (not HTML) with no `Accept` header, renders HTML for real browsers, renders the bare fragment for `HX-Request` |

A real bug was caught by writing the "JSON by default" test: `HttpRequest.accepts("text/html")`
returns `True` when no `Accept` header is sent at all (it falls back to
matching `*/*`), which would have silently sent monitoring probes a full
HTML page. Fixed in `apps/core/views.py` by checking for the literal
substring `"text/html"` in the raw header instead — see the comment there.

## Testing custom error pages

Django's custom `handler403`/`handler404`/`handler500` only fire when
`DEBUG = False` — with `DEBUG = True` (the dev default) Django shows its
own technical debug page instead, by design. Tests use
`@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])` (404) or
call the handler view functions directly with `RequestFactory` (403/500,
via the `rf` fixture) rather than trying to actually trigger a genuine
`PermissionDenied`/`500` through the full URL/middleware stack.

## Factories

`apps/accounts/tests/factories.py` — `UserFactory`. Uses
`skip_postgeneration_save = True` plus an explicit `self.save()` inside the
`password` post-generation hook (factory_boy would otherwise save twice
and emit a deprecation warning).

## Not yet covered (no code exists yet to test)

Selector tests, service tests, and permission/policy tests are listed in
the Phase 00 testing strategy but have no subject to test until the first
domain app (`organization`/`employees`) exists — see
[testing-strategy.md](testing-strategy.md) for what those will look like.
