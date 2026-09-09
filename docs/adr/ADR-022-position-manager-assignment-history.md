# ADR-022: Position & Manager Assignment as Separate Historical Tables

Status: Accepted (Phase 04)

## Context

An employee's position and their manager both need full history ("where did this person work, and under whom, on any given date" — Phase 04 brief §19, §26), not just a current value. Two shapes were possible:

1. One bundled table capturing position + manager (+ department/restaurant) together per effective period, as `docs/database/domain-model.md`'s Phase 00 sketch proposed for its own speculative `EmployeeAssignmentHistory`.
2. Two separate tables — `EmployeePositionAssignment` and `EmployeeManagerAssignment` — as Phase 04's brief explicitly and repeatedly describes (§18-§26, and the Final Architecture diagram in §the brief itself shows them as distinct entities).

## Decision

Two separate tables, per the current brief. Reasons this is now clearly correct, beyond just "the brief says so":

- **`Position` is now a first-class, rich entity** (Phase 03) — it already carries `job`, `department`/`organization_unit`, and `reports_to`. Phase 00's sketch predates Phase 03 and modeled the assignment row's own `position_title` as a plain string plus a `job_grade` FK — there was no equivalent to today's `Position` to point at instead. Bundling doesn't fit that shape anymore.
- **Secondary/acting/temporary assignments** (brief §21) can exist without a manager change, and a manager change can happen without any position change (a straight re-org). A single bundled row can't represent "two concurrent position assignments, one manager" — Phase 04 brief §21 explicitly requires supporting more than one concurrent assignment per employee (`is_primary` distinguishes which one drives `Employee.current_position`).
- Each table is independently effective-dated (`start_date`/`end_date`, `end_date IS NULL` = ongoing), so "who reported to whom on date X" and "what position did they hold on date X" are each a one-table lookup, and changing one never risks corrupting the other's timeline.

## Consequences

- `Employee.current_position` / `Employee.current_manager` are **denormalized pointers**, kept in sync exclusively by `EmployeeAssignmentService` / `EmployeeManagerService` inside the same transaction as the assignment row they mirror. Source of truth for history is always the assignment tables; the pointers exist purely so scoping (`apps/employees/permissions.py`) and list/detail rendering don't need a subquery per row. A dedicated consistency point: both services always update the pointer and the assignment row in the same `@transaction.atomic` block — see `apps/employees/services/assignment.py` and `manager.py`.
- Each table enforces "at most one active primary row per employee" via a partial `UniqueConstraint` (`is_primary=True, end_date__isnull=True`), not application-level checking alone (Phase 04 brief §20, §57).
- Cycle prevention for `EmployeeManagerAssignment` (`apps/employees/validators.py:assert_no_manager_cycle`) walks the *current*-manager chain (`Employee.current_manager`), not the full historical table — this is the same pattern `apps.organization.validators.assert_no_cycle` uses for `OrganizationUnit.parent`/`Position.reports_to`, adapted because "who currently manages X" isn't a plain self-FK here, it's derived from the assignment table via the synchronized pointer.
- `apps.organization.models.Department` and `Position` still deliberately have no `manager`/`employee` field (Phase 03's ADR-019 boundary) — the assignment tables are the only place an Employee↔Position/Employee↔Employee relationship is recorded.
