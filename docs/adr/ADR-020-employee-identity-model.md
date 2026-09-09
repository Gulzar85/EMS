# ADR-020: Employee Identity Model — Person Layer Deferred

Status: Accepted (Phase 04)

## Context

`docs/database/domain-model.md`, written in Phase 00 before any concrete app existed, sketched a three-way `Person` / `Employee` / `User` split specifically to handle rehire cleanly: `Person` holds identity once; `Employee` is *a period of employment* (a rehire creates a second `Employee` row pointing at the same `Person`); `User` optionally links to `Person`.

Phase 04's brief is far more detailed than that Phase 00 sketch, and describes a different shape throughout: `Employee` directly carries identity fields (name, DOB, gender, nationality — §7), `Employee.user` is a direct optional link (§49-§51), and nowhere does it mention a `Person` layer. It does not ask this phase to solve rehire.

## Decision

Phase 04 implements `Employee` as the direct identity + employment record — no separate `Person` model. `Employee.user` is a nullable `OneToOneField` to `accounts.User`. This matches the current, far more detailed brief exactly, and avoids introducing an entire unrequested app/model for a scenario (rehire) not in this phase's actual requirements — consistent with this project's repeated instruction not to build for hypothetical future requirements.

This does **not** abandon Phase 00's underlying concern. If rehire-as-a-first-class-scenario becomes a real requirement later, the migration is additive and mechanical, not a redesign:

1. Create a `people.Person` model holding the fields that are true of the *person*, not the *employment period* (name, DOB, nationality, gender — everything currently on `Employee` except `employee_number` and the FKs to `EmployeeContact`/`EmployeeEmployment`).
2. Add `Employee.person` (FK, `on_delete=PROTECT`).
3. Move the moved-out fields off `Employee` in the same migration.
4. A rehire becomes "create a new `Employee` row pointing at the existing `Person`" — exactly Phase 00's original design, arrived at when there's an actual rehire requirement to build against, not speculatively now.

Nothing else in Phase 04's schema (`EmployeeContact`, `EmployeeEmployment`, `EmployeePositionAssignment`, `EmployeeManagerAssignment`, `EmergencyContact`) needs to change for that migration — they all already FK to `Employee`, which keeps its `public_id` and `employee_number` unchanged.

## Consequences

- One `Employee` row per person, today. Rehire is not supported as a distinct modeled scenario in Phase 04 — a rehired person gets a new `Employee` row with a new `employee_number`, with no link back to their prior record. This is an accepted, explicit gap, not a silent one.
- `apps/accounts/models.py`'s own docstring (Phase 00-era) says "Employee will be introduced in a later phase as its own model, optionally linked to a User" — this is honored literally; the docstring's cross-reference to `docs/database/domain-model.md`'s Person/Employee/User split is superseded by this ADR for the shape of `Employee` itself, while the *reasoning* in that document (why rehire deserves a clean model, eventually) remains valid and is exactly what step 1-4 above implements when needed.
