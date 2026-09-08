# EMS — Employee Management System (McDonald's Pakistan)

**Phase 01: Django Foundation & Engineering Infrastructure.** This is the
technical foundation only — no business domains (Employees, Organization,
Leave, Attendance, ...) are implemented yet. See
[docs/architecture/system-architecture.md](docs/architecture/system-architecture.md)
for the full Phase 00 architecture this is built on.

## Technology stack

| Technology | Purpose |
|---|---|
| Python 3.12, Django 6.1 | Application framework |
| PostgreSQL 18 | Database |
| psycopg 3 | PostgreSQL adapter |
| django-environ | Environment-based settings (`DATABASE_URL`, secrets) |
| django-crispy-forms + crispy-tailwind | Form rendering |
| django-cotton | `<c-button>`/`<c-card>`/`<c-badge>` reusable components |
| django-axes | Login brute-force protection |
| Tailwind CSS v4, Alpine.js, htmx | Frontend — server-rendered, no SPA framework |
| Lucide (vendored SVGs) | Icons |
| pytest, pytest-django, factory_boy | Testing |
| Ruff | Linting + formatting |

Full stack rationale, and what was deliberately **not** installed yet
(`django-filter`, Celery, Sentry, django-storages) and why, is in the
Phase 01 plan / final report.

## Requirements

- Python 3.12+
- PostgreSQL running locally (or reachable via `DATABASE_URL`)
- Node.js 20+ (Tailwind CSS build only)

## Quick start (Windows / Git Bash)

```bash
# 1. Virtual environment (one already exists at venv/ in this repo)
venv/Scripts/pip install -e ".[dev]"

# 2. Environment file
cp .env.example .env
# fill in SECRET_KEY and DATABASE_URL — see docs/development/setup.md

# 3. Database
#   CREATE ROLE ems_dev WITH LOGIN PASSWORD 'change-me' CREATEDB;
#   CREATE DATABASE ems_dev OWNER ems_dev;
venv/Scripts/python manage.py migrate
venv/Scripts/python manage.py seed_core   # creates admin@example.local / changeme123!

# 4. Frontend build
npm install
npm run build

# 5. Run
venv/Scripts/python manage.py runserver
```

Visit `http://localhost:8000/` — you'll land on the login page.

Full walkthrough: [docs/development/setup.md](docs/development/setup.md).

## Running tests

```bash
venv/Scripts/python -m pytest
```

See [docs/development/testing.md](docs/development/testing.md).

## Code quality

```bash
venv/Scripts/python -m ruff check .
venv/Scripts/python -m ruff format .
pre-commit install   # once, to run these automatically on commit
```

## Project structure

```
config/            Django project config (settings/, urls.py, wsgi/asgi)
apps/
  core/             Cross-cutting foundation: mixins, middleware, health checks,
                    logging, icon tag, error pages. No business models.
  accounts/         Custom email-based User model. Auth identity only —
                    NOT the future HR "Employee" entity.
  theme/            Empty placeholder — Phase 02 (Dynamic Theme Engine) lands here.
templates/          base/ layouts/ components/ partials/ pages/
static/             src/ (edit) vendor/ (pinned JS, don't edit) dist/ (build output)
tests/              Cross-cutting tests (health, home, error pages)
docs/               Full architecture + Phase 01 implementation docs
```

Full app-by-app rationale: [docs/architecture/django-app-map.md](docs/architecture/django-app-map.md).

## Architecture documentation

- [docs/README.md](docs/README.md) — index of the full Phase 00 architecture package
- [docs/architecture/frontend-architecture.md](docs/architecture/frontend-architecture.md)
- [docs/architecture/theme-architecture.md](docs/architecture/theme-architecture.md)
- [docs/security/authorization.md](docs/security/authorization.md)
- [docs/development/setup.md](docs/development/setup.md), [frontend.md](docs/development/frontend.md), [testing.md](docs/development/testing.md) — Phase 01 specifics
