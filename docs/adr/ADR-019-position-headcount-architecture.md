# ADR-019: Position Headcount Architecture & the Employee/EmployeeAssignment Seam

## Status
Accepted

## Context

Phase 03 explicitly must not implement Employee Management (§7, §74-75), but `Position` needs to support workforce planning today: authorized headcount, vacancy, and utilization. Getting the boundary wrong — e.g. a direct `Position.employee` field — would force a redesign the moment Phase 04 introduces `Employee`.

## Decision

`Position` stores only `headcount_limit` (an authorized seat count — one row can represent several identical seats, e.g. 15 Crew Member seats at one restaurant, not 15 rows). `occupied_headcount`, `vacant_headcount`, `vacancy_rate`, and `utilization_rate` are model **properties**, computed, never stored (§26-27 explicitly asks for this). Today, `occupied_headcount` always returns `0` — there is no `EmployeeAssignment` model yet to count — implemented as exactly one property with a comment pointing at this ADR, not scattered across call sites:

```python
@property
def occupied_headcount(self) -> int:
    return 0  # Phase 04 seam — see ADR-019
```

The intended Phase 04 shape (documented here, not built): `Employee` (person + employment status) and a separate `EmployeeAssignment` join model (`employee`, `position`, `effective_from`, `effective_to`) — never a direct `Position.employee` FK, because a position can rotate occupants over time and, per `headcount_limit > 1`, may have multiple simultaneous occupants. When `EmployeeAssignment` exists, `occupied_headcount` becomes one query (`self.assignments.filter(effective_to__isnull=True).count()`) — a one-line change, not a schema migration on `Position` itself.

No `Department.manager` field exists yet for the same reason (§18) — it will be a FK to `Employee` once that model exists, added additively.

No `PositionHistory` table is built in Phase 03 (§50 explicitly allows deferring this) — `Position.effective_from`/`effective_to` exist so a position itself can be time-bounded, but tracking every department/manager/status change over time as its own historical record is deferred; when built, it should follow the same effective-dated pattern already established for `ThemeVersion` (Phase 02) rather than inventing a new one.

## Alternatives Considered

- **`Position.employee` (direct FK)** — rejected outright per §74: cannot represent an unfilled seat, cannot represent `headcount_limit > 1`, cannot represent employment history across occupants.
- **Building `EmployeeAssignment` now, ahead of `Employee`** — rejected: a join model with nothing to join to is speculative scaffolding for a model that doesn't exist, contrary to §95's anti-over-engineering guidance; better to design the seam clearly (this ADR) and build it for real in Phase 04 alongside `Employee`.
- **Building full `PositionHistory` now** — rejected per §50's own explicit permission to defer; the current fields (`effective_from`/`effective_to`, plus the audit log's field-level `position.updated`/`position.activated`/etc. entries via `apps.audit`) already provide a reasonable trail without the added modeling cost.

## Consequences

**Positive**: Phase 04 can introduce `Employee` and `EmployeeAssignment` additively — no migration touches `Position`'s existing columns, and every "0 occupied" reading in Phase 03's UI is honest (the detail page explicitly notes headcount will become accurate once assignments exist, rather than silently implying today's 0 is real data).

**Negative**: vacancy/utilization figures shown in Phase 03 are not yet meaningful for planning (every active position reads 100% vacant) — acceptable for a foundation phase, and clearly labeled as such in the UI rather than presented as if authoritative.
