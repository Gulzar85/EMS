# Position Management

Status: **Implemented (Phase 03)**. See [ADR-017](../adr/ADR-017-job-vs-position.md) (job vs. position) and [ADR-019](../adr/ADR-019-position-headcount-architecture.md) (headcount architecture, the Employee/EmployeeAssignment seam) for full rationale.

## Position ≠ Job ≠ Employee

- **Job** = the role ("Restaurant Manager") — see [job-architecture.md](job-architecture.md).
- **Position** = a specific, addressable seat ("MCD-0001-REST-MGR") — this document.
- **Employee** = who (if anyone) occupies that seat — **does not exist yet** (Phase 04).

A `Position` exists and can be planned, activated, and reported on entirely independently of whether anyone has ever been hired into it.

## Fields

`job` (FK, required), `organization_unit` and/or `department` (at least one required — a position anchors into the org structure directly via `organization_unit` for corporate-level seats, or via `department` for most restaurant/facility-level seats), `reports_to` (FK to another `Position`, not another `Job` — reporting lines connect specific seats), `code` (unique), `title`, `position_type` (individual contributor / supervisory / management), `status`, `headcount_limit`, `effective_from`/`effective_to`.

`headcount_limit` can be greater than 1 — one Position row can represent several identical authorized seats (e.g. "Crew Member, Restaurant #0001" with `headcount_limit=15`), avoiding 15 near-duplicate rows. This is deliberate, matching how restaurant staffing actually works.

## Lifecycle

```
DRAFT → ACTIVE ⇄ FROZEN
  ↓        ↓        ↓
      CLOSED (from ACTIVE or FROZEN)
```

Transitions go through `apps/organization/services.py`, never a bare `.save()`:

| Action | Valid from | Result |
|---|---|---|
| Activate | DRAFT | ACTIVE |
| Freeze | ACTIVE | FROZEN |
| Unfreeze | FROZEN | ACTIVE |
| Deactivate | ACTIVE or FROZEN | CLOSED |
| Duplicate | any status | creates a **new** DRAFT position (never copies the source's status — a duplicate of an ACTIVE position starts as DRAFT, requiring its own explicit activation) |

Each service function validates the current status before transitioning (e.g. `freeze_position` raises `OrganizationValidationError` if the position isn't currently ACTIVE) and records the transition via `apps.audit.services.record()` in the same transaction.

There is deliberately no stored `Vacant` status — vacancy is always computed (see below), never a fifth `status` value, per the Phase 03 brief's own instruction to avoid duplicated state.

## Headcount — what's real today and what isn't

`Position` exposes four computed properties: `occupied_headcount`, `vacant_headcount`, `vacancy_rate`, `utilization_rate`. **`occupied_headcount` always returns `0` today** — there is no `EmployeeAssignment` model yet to count real occupants against. This is intentional and documented, not a bug: every position in Phase 03 reads as 100% vacant, and the UI says so explicitly (the Position detail page shows a note: *"Occupied headcount will reflect real employee assignments starting in Phase 04"*) rather than silently implying the 0 is meaningful workforce data.

```python
@property
def occupied_headcount(self) -> int:
    return 0  # Phase 04 seam — see ADR-019
```

## The Phase 04 seam (read before building Employee)

When `Employee` and a separate `EmployeeAssignment` join model (`employee`, `position`, `effective_from`, `effective_to`) exist, `occupied_headcount` becomes one query:

```python
@property
def occupied_headcount(self) -> int:
    return self.assignments.filter(effective_to__isnull=True).count()
```

**Never** add a direct `Position.employee` field — a position can have `headcount_limit > 1` (multiple simultaneous occupants) and can rotate occupants over time; a 1:1 FK cannot represent either. Likewise `Department.manager` will be a FK to `Employee`, added additively once that model exists — not a placeholder field today.

## No `PositionHistory` table yet

Field-level history of a position's own changes (department reassignment, manager changes, status transitions) is captured today only via the custom audit log (`apps.audit`) — one row per meaningful change, not a queryable temporal table. A dedicated `PositionHistory` model is an explicit Phase 04+ extension (see ADR-019), deferred per the Phase 03 brief's own permission to do so. When built, it should follow the same effective-dated pattern already established for `ThemeVersion` (Phase 02), not a new pattern.

## Reporting lines and cycle prevention

`Position.reports_to` is validated the same way `OrganizationUnit.parent` and `Department.parent` are — via the shared `apps/organization/validators.py:assert_no_cycle()` helper — rejecting both self-reference and any longer cycle.
