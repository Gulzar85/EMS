# ADR-008: Effective Dating Strategy

## Status

Accepted

## Context

An employee's position, restaurant assignment, manager, department, job grade, and salary all change over time, and none of that history may ever be silently overwritten. The system must be able to answer "what was true on date X" for any point in the past, and must support changes that are scheduled to take effect in the future (e.g., a promotion effective the first of next month).

## Decision

Every historical table carries `effective_from` (required) and `effective_to` (nullable — null means open-ended/current) fields describing the period during which that row was the true value.

A PostgreSQL **`ExclusionConstraint`** on the date range, scoped per employee and per history type, prevents overlapping periods from ever existing — enforced at the **database level**, not merely by application validation (this is enabled by the choice of PostgreSQL in ADR-002).

"Current" is defined as the row whose `[effective_from, effective_to)` range contains today's date. Future-dated rows are explicitly permitted and become "current" automatically once their `effective_from` date arrives — no batch job is required to "activate" them. All effective-dated writes — closing the previous row and opening the new one — happen inside a single `transaction.atomic()` service call, so the operation is always atomic from the database's point of view.

## Alternatives Considered

- **Overwriting the current row and relying on `django-simple-history` for history** — rejected. `django-simple-history`'s historical records are a change-log/audit trail of a mutable row, not a first-class effective-dated query surface. You cannot cleanly ask "what will Employee X's restaurant assignment be three months from now" against a change-log the way you can against a proper effective-dated table. The two mechanisms serve genuinely different purposes; EMS needs the effective-dated table as the source of truth for "what is/was/will be true," with `simple-history` layered on top as a secondary audit trail (see ADR-009).
- **App-level-only overlap validation with no database constraint** — rejected. Without a database-level guarantee, race conditions between concurrent requests could still create overlapping or gapped records. The architecture brief explicitly calls for transaction and uniqueness rules to be defined, not merely a "best effort" application check.

## Consequences

**Positive:**
- Database-enforced correctness: no possible overlapping or gapped history can arise from an application bug or a race condition between concurrent writers.
- Future-dated changes are supported naturally, with no separate "activation" mechanism needed.
- Clean "as of" queries are possible against a single, well-structured table per history type.

**Negative / Tradeoffs:**
- Every effective-dated write is inherently more complex than a plain `.save()` — it must close the prior row and validate that no overlap is created. This complexity is precisely why each entity type's effective-dating logic is wrapped in a single service function rather than left to ad hoc view code: the complexity is paid once per entity type at the service layer, not repeated at every call site that needs to make such a change.
