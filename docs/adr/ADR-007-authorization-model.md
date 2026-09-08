# ADR-007: Authorization Model

## Status

Accepted

## Context

The architecture brief explicitly warns against naive authorization checks such as `user.is_staff` or `user.role == "HR"`, and requires scope-aware access control across the organizational hierarchy: Global, Region, Area, Restaurant, Department, and Self. The canonical example driving this decision: a Restaurant Manager should be able to see the employees at their own restaurant, but must not automatically be able to see those employees' salaries — visibility of an employee and visibility of that employee's compensation are two independent concerns.

## Decision

EMS uses a **two-layer authorization model**:

1. **Django Groups/Permissions** provide coarse capability checks — e.g., `view_employee`, `view_compensation`, `approve_leave` — answering "can this user, in principle, do this kind of thing at all."
2. A custom **`UserScope(user, scope_type, scope_id)`** model captures *where* that capability applies, with `scope_type` in `{GLOBAL, REGION, AREA, RESTAURANT, DEPARTMENT, SELF}`.

Each domain app defines its own `policies.py` combining both layers into a single answer for a given user, action, and target object. Policies are enforced in **selectors** at read time (scope-filtering query results by default) and in **services** at write time (rejecting a write outside the caller's scope) — never in templates, where a check could be accidentally omitted from one rendering path but not another.

Compensation visibility is treated as a fully independent permission from employee visibility, reinforced structurally by keeping `compensation` as a separate Django app from `employees` — so "can view this employee" and "can view this employee's salary" are never the same check.

## Alternatives Considered

- **django-guardian for object-level permissions** — rejected. Guardian's per-object grant model doesn't naturally express "everything under this Area" without granting access to every individual Restaurant and Employee row one by one — an unworkable operational burden given this organization's hierarchy depth and headcount. The custom hierarchy-shaped `UserScope` model is a much better structural fit.
- **A single flat role field on `User`** (e.g., `user.role`) — rejected. This is exactly the pattern the architecture brief warns against: it cannot express "Restaurant Manager for Restaurant X but not Restaurant Y," and it cannot cleanly separate "can see this employee" from "can see this employee's salary" without an unmanageable explosion of ad hoc role strings.

## Consequences

**Positive:**
- Precisely expresses the org-hierarchy-shaped access model this business actually has, rather than approximating it with roles.
- Cleanly separates coarse capability, geographic/organizational scope, and field-level sensitivity (e.g., compensation) as independent, composable concerns.
- Policy functions are pure functions and are straightforward to unit test in isolation from views or templates.

**Negative / Tradeoffs:**
- More moving parts than a single role field. Every new sensitive view or service must remember to call the correct policy function — a real discipline requirement. This is mitigated by having selectors perform scope-filtering by default for reads, making the safe behavior the path of least resistance ("opt-out-proof") rather than something each view must remember to opt into.
- The `UserScope` model requires its own assignment UI and administrative workflow to be designed and built, and — because permission changes are on the required-audit list (ADR-009) — every change to a user's scope must itself be audited.
