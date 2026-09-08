# Local development setup (Phase 01)

Written for Windows, matching this project's actual dev environment
(PowerShell/Git Bash, a `venv/` already at the repo root, local PostgreSQL 18).

## Prerequisites

- Python 3.12+
- PostgreSQL running locally (or reachable via `DATABASE_URL`)
- Node.js 20+ (only used to build Tailwind CSS — see [frontend.md](frontend.md))

## 1. Virtual environment

A `venv/` already exists at the repo root. If you need to recreate it:

```bash
python -m venv venv
venv/Scripts/pip install -e ".[dev]"
```

(`pip install -e ".[dev]"` reads `pyproject.toml` — see the dependency table in
the Phase 01 summary for what each package is for and why.)

## 2. Environment file

```bash
cp .env.example .env
```

Fill in `SECRET_KEY` (generate one: `venv/Scripts/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
and `DATABASE_URL`. Never commit `.env`.

## 3. Database

Create a dedicated role and database (adjust the password):

```sql
CREATE ROLE ems_dev WITH LOGIN PASSWORD 'change-me' CREATEDB;
CREATE DATABASE ems_dev OWNER ems_dev;
```

Then point `DATABASE_URL` in `.env` at it:

```
DATABASE_URL=postgresql://ems_dev:change-me@127.0.0.1:5432/ems_dev
```

## 4. Migrate and seed

```bash
venv/Scripts/python manage.py migrate
venv/Scripts/python manage.py seed_core
```

`seed_core` creates one fake dev superuser: `admin@example.local` /
`changeme123!`. It refuses to do anything if that user already exists, and
it must never be pointed at a real environment — see
[docs/security/audit.md](../security/audit.md) for why real employee data
never belongs in fixtures or seed scripts.

## 5. Frontend build

See [frontend.md](frontend.md) for details. Quick version:

```bash
npm install
npm run build
```

## 6. Run the server

```bash
venv/Scripts/python manage.py runserver
```

Visit `http://localhost:8000/` — you'll be redirected to `/accounts/login/`.

## 7. Tests and linting

```bash
venv/Scripts/python -m pytest
venv/Scripts/python -m ruff check .
venv/Scripts/python -m ruff format .
```

See [testing.md](testing.md) for what's covered at each layer.

## Settings modules

`DJANGO_SETTINGS_MODULE` defaults to `config.settings.development` (set in
`manage.py`/`wsgi.py`/`asgi.py`). Override it explicitly for other
environments, e.g.:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production venv/Scripts/python manage.py check --deploy
```
