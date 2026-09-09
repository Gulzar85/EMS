# ADR-017: Job vs. Position Architecture

## Status
Accepted

## Context

Workforce planning, recruitment, transfers, and headcount reporting all need to distinguish "the role" from "the seat." A `Job` ("Restaurant Manager") describes a kind of work — its family, level, and employment category — independent of where or how many times it exists in the organization. A `Position` ("RM-LHR-001") is a specific, addressable seat at a specific place, with its own lifecycle (draft → active → frozen/closed) and headcount limit, that may or may not currently be occupied. Conflating these (e.g. one row per employee, keyed by job title) makes it impossible to represent an authorized-but-vacant seat, or to plan headcount before recruiting.

## Decision

Two separate models. `Job` (`apps/organization/models/job.py`) carries `job_family` (FK to `JobFamily`, real admin-manageable master data), `job_level` (FK to `JobLevel`, ditto, ordered by `rank`), and `employment_category` (a `TextChoices` — full-time/part-time/contract/intern/temporary — a genuinely fixed HR category, not something requiring admin reconfiguration, so a `TextChoices` rather than a master-data table). `Position` (`apps/organization/models/position.py`) FKs to exactly one `Job`, anchors into the org structure via `organization_unit` and/or `department`, tracks its own `status`, `headcount_limit`, `position_type`, and an optional `reports_to` (another `Position`, not another `Job` — reporting lines are between specific seats, e.g. "this Shift Leader seat reports to that Restaurant Manager seat").

`headcount_limit` on `Position` means a single position row can represent *N* authorized seats of the same kind at the same place (e.g. one "Crew Member, Restaurant #123" position with `headcount_limit=15`), avoiding 15 near-identical rows — this is deliberate, not an oversight (see ADR-019 for how occupied/vacant counts derive from this).

`JobFamily`/`JobLevel` are real database rows (not `TextChoices`) because they are genuinely business-configurable — HR may add a new family or insert a level without a code deployment; `Position.status`/`position_type` and `Job.employment_category` stay `TextChoices` because they're fixed technical states any deployment of this system would share.

## Alternatives Considered

- **One combined `Job`/`Position` model** — rejected: cannot represent an authorized-but-unfilled seat distinctly from "this role doesn't exist here," which breaks vacancy/headcount reporting entirely.
- **`JobFamily`/`JobLevel` as `TextChoices`** — rejected: these are exactly the kind of business-configurable master data Phase 00's own database conventions doc distinguishes from fixed technical states; hardcoding them would mean a code deploy every time HR restructures job families.
- **`Position.reports_to` pointing at `Job` instead of `Position`** — rejected: reporting lines exist between actual seats at actual locations ("this specific Shift Leader reports to that specific Restaurant Manager at Restaurant #123"), not between abstract role descriptions.

## Consequences

**Positive**: clean separation supports workforce planning (positions can be created before anyone is hired), vacancy reporting (a position simply has no occupant yet), and org-chart reporting lines expressed at the correct granularity (seat-to-seat).

**Negative**: creating a new restaurant role requires two steps conceptually (ensure the `Job` exists, then create a `Position` referencing it) rather than one — a deliberate cost for the flexibility gained; the seed command (`seed_organization`) demonstrates the expected two-step pattern.
