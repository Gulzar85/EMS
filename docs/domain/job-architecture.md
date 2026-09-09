# Job Architecture

Status: **Implemented (Phase 03)**. See [ADR-017](../adr/ADR-017-job-vs-position.md) for the job-vs-position rationale; [position-management.md](position-management.md) for how `Job` connects to `Position`.

## Models

- **`JobFamily`** — a broad grouping (e.g. "Restaurant Operations", "Corporate Support"). Real master data (admin-manageable rows), not a `TextChoices`, because HR genuinely adds/renames families over time without a code deploy.
- **`JobLevel`** — an ordered rank (`rank` field, unique, drives default list ordering) with a name (e.g. "L1 — Entry" through "L4 — Manager"). Also real master data.
- **`Job`** — the role description itself: `code`, `title`, `description`, `job_family` (FK), `job_level` (FK), `employment_category` (`TextChoices`: full-time/part-time/contract/intern/temporary/other — a fixed HR category, not business-configurable, hence a choices field rather than a table).

## Why `employment_category` is a `TextChoices` but `JobFamily`/`JobLevel` are tables

Per the project's existing convention (`docs/database/database-conventions.md`): choices for genuinely fixed technical states, master-data tables for business-configurable values. Full-time/part-time/contract are about as fixed as HR categories get across any deployment of this system. Job families and levels are exactly the kind of thing McDonald's Pakistan HR will want to restructure without waiting on a code change.

## No compensation logic here

Per the Phase 03 brief's own instruction, `Job`/`JobLevel` intentionally carry no salary/compensation fields — that's a distinct future domain (Phase 00's architecture docs already scoped a separate `compensation` app for this). `JobLevel.rank` exists purely for ordering/career-progression display today.

## Global, not organization-scoped

Unlike `Location`/`Restaurant`/`Department`/`Position`, `JobFamily`/`JobLevel`/`Job` are **not** filtered by `apps.organization.permissions` — a "Crew Member" job description isn't tied to one restaurant, region, or area. Every authenticated user with `organization.view_job` (etc.) sees the full job catalog regardless of their `UserScope` rows.

## Deletion

`JobFamily`/`JobLevel` are `PROTECT`ed by `Job.job_family`/`Job.job_level`; `Job` is `PROTECT`ed by `Position.job`. Deleting one that's still referenced is refused with a friendly in-app message (not a 500), matching every other delete flow in this app — deactivate (`is_active=False`) instead of deleting when historical positions still reference a job.
