# ADR-023: Employee Lifecycle & the Single Status Source of Truth

Status: Accepted (Phase 04)

## Context

Phase 04 brief §17 explicitly warns against two independently-editable status fields that can contradict each other (`Employee.is_active = True` while `Employment.status = Terminated`). It also asks for a "clean state model" (§27), not a full workflow engine, and for activation/deactivation to be explicit, auditable actions (§28-§30), not free-form field edits.

## Decision

**`Employee` has no `is_active` field.** `Employee.is_active` is a computed Python property reading `EmployeeEmployment.status`:

```python
@property
def is_active(self) -> bool:
    employment = getattr(self, "employment", None)
    return bool(employment) and employment.status in CURRENTLY_EMPLOYED_STATUSES
```

This makes the two-independently-editable-fields problem structurally impossible rather than a discipline to maintain — there is only ever one status value to read.

**Lifecycle states** (`EmployeeEmployment.Status`): `DRAFT → PROBATION (if probation_end_date set) → ACTIVE ⇄ ON_LEAVE`, `ACTIVE ⇄ SUSPENDED`, and `{PROBATION, ACTIVE, ON_LEAVE, SUSPENDED} → {RESIGNED, TERMINATED, RETIRED}` (terminal). This mirrors `Position`'s own `DRAFT → ACTIVE ⇄ FROZEN → CLOSED` pattern from Phase 03 exactly, extended for the extra states an employee (vs. a position) genuinely needs.

Every transition is a named `EmployeeLifecycleService` method (`activate`, `confirm`, `place_on_leave`, `return_from_leave`, `suspend`, `reinstate`, `deactivate`) that validates the current status, writes the new one plus any transition-specific fields (`confirmation_date` on confirm; `termination_date`/`termination_reason` on deactivate) inside one `@transaction.atomic` block, and audits the change — never a bare `employee.employment.status = "..."; save()` from a view or form.

## Consequences

- No `PENDING`/`INACTIVE` catch-all states were added — `DRAFT` covers pre-activation, and the three terminal states (`RESIGNED`/`TERMINATED`/`RETIRED`) already cover every kind of exit this phase needs to represent, avoiding an ambiguous fifth "just inactive" bucket the brief's own §15 warns against over-building.
- `EmployeeCreateForm`/`EmployeeProfileForm` (the generic create/edit forms) never expose `status`, `confirmation_date`, or `termination_date` — those are reachable only through the seven lifecycle CBVs (`apps/employees/views/lifecycle.py`), each permission-gated on `employees.change_employee` and each producing its own audit event (`employee.activated`, `.confirmed`, `.placed_on_leave`, `.returned_from_leave`, `.suspended`, `.reinstated`, `.deactivated`).
- Not a workflow engine: there's no configurable state machine, no per-tenant transition rules, no approval steps. Seven fixed Python methods are the entire lifecycle surface — sufficient for this phase, and a future onboarding/workflow phase (Phase 05, per the brief's own "Phase 05 Readiness" section) can layer richer process on top without this core state model changing.
