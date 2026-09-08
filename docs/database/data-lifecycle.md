# Data Lifecycle — Effective Dating, Overlap Enforcement & Retention

Status: Final (Phase 00 architecture package)
Related documents: [`./database-conventions.md`](./database-conventions.md) · [`./domain-model.md`](./domain-model.md)

This document is the technical deep-dive for every effective-dated table in EMS — `EmployeeAssignmentHistory`, `SalaryHistory`, and any future table of the same shape (e.g. a future `LeaveBalanceHistory`). It specifies field shape, database-enforced overlap prevention, the standard query patterns, transaction behavior, and the retention/lifecycle rules for historical and terminated-employee data.

---

## 1. Field Shape

Every effective-dated table carries exactly these two fields for its validity period:

```python
effective_from = models.DateField()
effective_to = models.DateField(null=True, blank=True)
```

- `effective_from` — the first day the row is in effect. Always required.
- `effective_to` — the last day the row is in effect, **inclusive**. `NULL` is a meaningful value: it means "open-ended / currently in effect," i.e. this row has not yet been superseded. See §5 on the nullable-field policy rationale in [`./database-conventions.md`](./database-conventions.md#5-nullable-field-policy) for why this is a `null=True` case and not a sentinel far-future date.

Both fields are `DateField`, not `DateTimeField` — effective dating in this system operates at day granularity (a transfer or raise takes effect *on a date*), never at a specific time of day.

---

## 2. Overlap Prevention: Postgres `ExclusionConstraint`

**Rule: no two rows for the same employee (within the same history table) may have overlapping effective date ranges.** This must be enforced at the database level, not just in application/service-layer validation — application validation can be bypassed by a bug, a bulk import, a direct DB fix, or a race between two concurrent requests; a DB constraint cannot.

Postgres's native tool for "no two rows may overlap on this range, for the same key" is `ExclusionConstraint` using a `daterange` and the `&&` (overlap) operator, combined with equality on the key column via `RangeOperators.OVERLAPS` and `RangeOperators.EQUAL`.

### 2.1 Conceptual constraint shape

For `EmployeeAssignmentHistory`:

```python
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.db.models import Func, F


class EmployeeAssignmentHistory(CoreModel):
    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="assignment_history"
    )
    restaurant = models.ForeignKey(
        "organization.Restaurant", on_delete=models.PROTECT, related_name="assignments"
    )
    department = models.ForeignKey(
        "organization.Department", on_delete=models.PROTECT, related_name="assignments"
    )
    job_grade = models.ForeignKey(
        "organization.JobGrade", on_delete=models.PROTECT, related_name="assignments"
    )
    manager = models.ForeignKey(
        "employees.Employee",
        on_delete=models.PROTECT,
        related_name="direct_report_assignments",
        null=True,
        blank=True,
    )
    position_title = models.CharField(max_length=150)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="assignment_effective_to_after_from",
            ),
            ExclusionConstraint(
                name="assignment_no_overlapping_periods_per_employee",
                expressions=[
                    ("employee", RangeOperators.EQUAL),
                    (
                        Func(
                            "effective_from",
                            "effective_to",
                            function="daterange",
                            template="daterange(%(expressions)s, '[]')",
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]
```

Conceptually, this compiles to the Postgres DDL:

```sql
ALTER TABLE employees_employeeassignmenthistory
    ADD CONSTRAINT assignment_no_overlapping_periods_per_employee
    EXCLUDE USING gist (
        employee_id WITH =,
        daterange(effective_from, effective_to, '[]') WITH &&
    );
```

Read as: "reject any insert/update that would produce two rows with the same `employee_id` whose date ranges overlap." The `'[]'` bound-type argument makes both `effective_from` and `effective_to` inclusive endpoints (a `NULL` upper bound in `daterange` is treated as unbounded/open-ended automatically, which is exactly the "current" semantics we want).

This requires the `btree_gist` extension (needed because the exclusion constraint mixes an equality comparison on a plain scalar column with a range-overlap comparison, which GiST needs `btree_gist` to support for the scalar side):

```python
# migration
from django.contrib.postgres.operations import BtreeGistExtension


class Migration(migrations.Migration):
    operations = [
        BtreeGistExtension(),
    ]
```

`SalaryHistory` gets the identical shape of constraint, keyed on `employee` as well (an employee cannot have two overlapping salary periods, independent of the assignment table — see [`./domain-model.md`](./domain-model.md#32-salaryhistory-is-deliberately-separate) for why they're separate tables in the first place).

**This is the authoritative enforcement mechanism.** Application-layer validation in the service functions below exists to produce a friendly error message before hitting the DB — the `ExclusionConstraint` is what actually guarantees the invariant holds, including against bulk imports, admin edits, and any code path that isn't the one "correct" service function.

---

## 3. Current-Record Determination

"Current" for any effective-dated row means: `effective_from` is on or before today, and `effective_to` is either `NULL` (open-ended) or strictly after today.

### 3.1 Query pattern

```python
from django.db.models import Q
from django.utils import timezone


def get_current_assignment(employee, as_of=None):
    as_of = as_of or timezone.localdate()
    return (
        EmployeeAssignmentHistory.objects.filter(employee=employee, effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=as_of))
        .order_by("-effective_from")
        .first()
    )
```

Equivalent raw SQL shape:

```sql
SELECT *
FROM employees_employeeassignmenthistory
WHERE employee_id = %(employee_id)s
  AND effective_from <= %(as_of)s
  AND (effective_to IS NULL OR effective_to > %(as_of)s)
ORDER BY effective_from DESC
LIMIT 1;
```

Because the `ExclusionConstraint` (§2) guarantees no overlapping rows exist, this query returns at most one row for any given `as_of` date — the `ORDER BY ... LIMIT 1` is a defensive safeguard, not something that should ever need to break a tie in practice.

This same `get_current_assignment(employee, as_of=...)` shape is mirrored as `get_current_salary(employee, as_of=...)` against `SalaryHistory`, and should be the standard selector pattern for any future effective-dated table — don't inline the `WHERE effective_from <= X AND (effective_to IS NULL OR effective_to > X)` condition ad hoc in views/serializers; put it behind a named selector function per table.

### 3.2 The partial index that backs this query

As specified in [`./database-conventions.md`](./database-conventions.md#42-partial-indexes-for-current-record-lookups), the "current row" case (`effective_to IS NULL`) is the overwhelming majority of lookups, so it gets its own partial index rather than relying on a full index across the whole history table:

```python
class Meta:
    indexes = [
        models.Index(
            fields=["employee"],
            name="empassign_current_idx",
            condition=models.Q(effective_to__isnull=True),
        ),
    ]
```

### 3.3 Historical ("as of") queries

The same selector function handles both "current" and "as of a past date" lookups via the `as_of` parameter — there is no separate code path for history vs. current:

```python
# "What was true on 2025-03-15?"
get_current_assignment(employee, as_of=date(2025, 3, 15))

# "What's true right now?" (as_of defaults to today)
get_current_assignment(employee)
```

To retrieve a full timeline (not just one point in time):

```python
def get_assignment_timeline(employee):
    return EmployeeAssignmentHistory.objects.filter(employee=employee).order_by("effective_from")
```

---

## 4. Future-Dated Changes

Future-dated changes are explicitly allowed. A transfer effective next Monday can — and in practice routinely will — be created today, ahead of the effective date. It will not show up as "current" via `get_current_assignment()` until that date actually arrives, because the `effective_from__lte=as_of` filter excludes it until then.

Creating a future-dated change follows the same close-old/open-new pattern as an immediate change (§5) — the only difference is that the new row's `effective_from` is a future date, and the currently-open row's `effective_to` is set to the day before that future date (not today):

```python
def schedule_assignment_change(
    employee,
    new_restaurant,
    new_department,
    new_job_grade,
    new_position_title,
    new_manager,
    effective_from,
    *,
    acting_user,
):
    with transaction.atomic():
        current = EmployeeAssignmentHistory.objects.select_for_update().get(
            employee=employee, effective_to__isnull=True
        )
        if effective_from <= current.effective_from:
            raise InvalidEffectiveDateError(
                "New effective date must be after the current period's start."
            )

        current.effective_to = effective_from - timedelta(days=1)
        current.save(update_fields=["effective_to", "updated_at"])

        return EmployeeAssignmentHistory.objects.create(
            employee=employee,
            restaurant=new_restaurant,
            department=new_department,
            job_grade=new_job_grade,
            position_title=new_position_title,
            manager=new_manager,
            effective_from=effective_from,
            created_by=acting_user,
        )
```

Because `effective_to` on the old row becomes `effective_from - 1 day` (not `NULL`, not today), the two rows are contiguous with no gap and no overlap — satisfying the `ExclusionConstraint` regardless of whether `effective_from` is today or several weeks out.

---

## 5. Transaction Behavior

**Closing the previous row and opening the new one always happens inside the same `transaction.atomic()` block**, in the same service call — never as two separate saves from application code that could partially fail. This is non-negotiable: if the "close old row" write succeeds but the "create new row" write fails (or vice versa), the employee would either have no current assignment at all, or two overlapping ones (which the `ExclusionConstraint` would then reject at exactly the wrong moment — mid-way through an otherwise-committed change).

The pattern is the same one used for immediate changes and future-dated changes alike (§4's `schedule_assignment_change` is the canonical example). `select_for_update()` on the current row being closed is used when there's a realistic chance of two concurrent requests trying to change the same employee's assignment at once (e.g. two HR admins editing the same employee simultaneously) — see [`./database-conventions.md`](./database-conventions.md#9-transactions-and-referential-integrity) for the general `select_for_update()` policy and a second worked example (leave balance approval).

---

## 6. Uniqueness Rules — Summary

- No two rows in the same effective-dated table may exist for the same employee with overlapping `[effective_from, effective_to]` ranges. **Enforced by the `ExclusionConstraint` in §2** — this is a database-level guarantee, not merely an application-level check.
- At most one row per employee, per table, may have `effective_to IS NULL` at any time (an employee has exactly one "current" assignment and exactly one "current" salary). This falls out automatically from the overlap constraint: a second open-ended row would necessarily overlap the first (an open range overlaps everything from its start date onward).
- Application-layer validation (checking for an existing open row before creating a new one, as shown in `schedule_assignment_change` above) exists purely to give a clean error message before the DB constraint would reject the write — it is a UX nicety layered on top of the real guarantee, not a substitute for it.

---

## 7. Retention & Lifecycle

### 7.1 Terminated employees remain historically reportable forever, by default

There is no automatic purge of employee data on termination. The lifecycle of a termination is:

1. `Employee.status` transitions to `TERMINATED`, `Employee.termination_date` is set.
2. The employee's currently-open `EmployeeAssignmentHistory` row gets a final `effective_to` (the last working day) — it becomes a closed historical row, not a deleted one.
3. `Person` and `Employee` rows are **never hard-deleted** (per the soft-deletion policy in [`./database-conventions.md`](./database-conventions.md#6-soft-deletion-policy) — employment history must remain reportable indefinitely by default, since HR reporting, compliance, and potential rehire all depend on it staying queryable).
4. `SalaryHistory` rows are likewise never deleted — they remain part of the permanent compensation record.

If the employee is later rehired, this is a **new** `Employee` row against the same `Person` (see [`./domain-model.md`](./domain-model.md#22-employee-app-employees--one-employment-record-per-period-of-employment)), not a reactivation of the old one — the old `Employee` row's terminal state (`TERMINATED`, its final assignment period, its final salary period) is preserved exactly as it was.

### 7.2 Soft-deleted reference data

Deactivated reference/lookup rows (a closed `Restaurant`, a retired `JobGrade`, etc.) follow the standard `core.SoftDeleteModel` mixin described in [`./database-conventions.md`](./database-conventions.md#61-softdeletemodel-mixin) — `is_active=False` plus `deactivated_at`, excluded from the default manager, still fully joinable from historical `EmployeeAssignmentHistory`/`SalaryHistory` rows that reference them (the FK uses `on_delete=PROTECT`, so a reference row cannot be hard-deleted out from under history it's linked to — see [`./database-conventions.md`](./database-conventions.md#8-cascade-policy)).

### 7.3 Retention *period* — explicitly out of scope for Phase 00

This document establishes that historical data is **not automatically purged** and defines how it stays queryable indefinitely by default. It does **not** define an actual retention time limit (e.g. "purge terminated-employee records after N years") — that number requires sign-off from Legal/Compliance and must reflect applicable Pakistani labor law and record-keeping requirements, none of which have been provided as input to this architecture phase.

**This is flagged as an explicit Phase 01 prerequisite input**, not invented here. Once Legal/Compliance supplies a retention period, it should be implemented as a scheduled purge/archival job operating on closed (`effective_to IS NOT NULL`) historical rows older than the retention cutoff, and on `Employee` rows whose `termination_date` predates the cutoff by the required margin — but no such job exists or should be built until that number is supplied. Do not default to an assumed number (e.g. "7 years") without that sign-off; treat the absence of a number as a blocker for building the purge job, not as license to guess.

### 7.4 Append-only log data

`AuditLog` and `IntegrationLog` (and similar purely transactional, naturally append-only tables) have no deletion concept in the application at all, per [`./database-conventions.md`](./database-conventions.md#6-soft-deletion-policy) — their retention is governed by the same Legal/Compliance-driven policy referenced in §7.3, not by any per-row application logic.
