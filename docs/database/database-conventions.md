# Database Conventions

Status: Final (Phase 00 architecture package)
Applies to: all Django apps in the EMS project, PostgreSQL target
Related documents: [`./domain-model.md`](./domain-model.md) · [`./data-lifecycle.md`](./data-lifecycle.md)

This document is the concrete, code-level reference for how every model in the EMS codebase must be built. It is written so that any engineer can implement a new model by following the patterns here without needing to re-derive the rationale. Where a decision has a non-obvious tradeoff, the reasoning is spelled out explicitly so nobody "simplifies" it back to something worse later.

---

## 1. Primary Key Strategy

**Decision: `BigAutoField` is the real primary key on every model. A separate, indexed, unique `public_id` (UUID) field exists only on models that are addressed by URL, exposed to end users, or exposed via an API.**

### 1.1 The real PK: `BigAutoField`

Django 6's project-wide default is used unconditionally:

```python
# settings.py
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

Every model gets an implicit 8-byte integer `id` column. Nothing overrides this to a UUID PK.

**Why:** the highest-volume child table in this system, `AttendanceRecord`, is on the order of *(number of employees) × (days) × (years)* rows — comfortably into the tens of millions over the system's lifetime. Two properties of `BigAutoField` matter at that volume:

- **Index size.** Every foreign key referencing a table carries a copy of that table's PK in its own index. An 8-byte `bigint` FK column (and its btree index) is half the size of a 16-byte `uuid` column doing the same job. Multiply that across every child table that points at `Employee`, and the difference is real disk, real cache-hit-rate, real join performance.
- **Insert locality.** `BigAutoField` values are monotonically increasing, so new rows are appended to the rightmost edge of the table's btree indexes. Random UUIDv4 values scatter inserts across the entire index, causing page splits and fragmentation that get worse as the table grows. On a table taking thousands of writes a day for years, this compounds.

### 1.2 The public identifier: `public_id`

On models that are ever put in a URL, returned to a browser/API client, or referenced outside the database, add:

```python
import uuid
from django.db import models


class Employee(CoreModel):
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    ...
```

Use `public_id` in URLs and API payloads (`/employees/<uuid:public_id>/`), never `pk`/`id`.

**Which models get a `public_id`:** anything user/URL/API-facing — confirmed examples: `Person`, `Employee`, `Document`, `LeaveRequest`, and any future model in the same category (recruitment applications once they're API-exposed, etc.).

**Which models do NOT get one:** purely internal, join-heavy, or backend-only tables that are never addressed directly by URL — `EmployeeAssignmentHistory`, `SalaryHistory`, `AuditLog`, `UserScope`, and similar. These are always reached *through* their owning entity (e.g. `/employees/<public_id>/assignment-history/`), so they don't need their own public identifier. Adding one would just be unused overhead.

### 1.3 Rejected alternatives (documented so nobody re-litigates this)

- **Alternative A — UUID as the actual PK everywhere.** Rejected. It bloats every FK index referencing that table (16 bytes vs. 8) and randomizes insert order on high-write child tables, for no benefit at this data volume. EMS is not a distributed, multi-writer system that needs collision-free client-generated IDs — it's a single Postgres primary serving a few thousand employees' worth of HR data. UUID-everywhere is solving a problem this system doesn't have, at a cost it will feel.
- **Alternative B — plain integer PK exposed directly in URLs.** Rejected. Sequential integer IDs are enumerable: `/employees/1042/` trivially implies `/employees/1041/` exists, and the gap between the smallest and largest ID observed over time leaks the organization's headcount and hiring/attrition rate to anyone probing the URL space. That's a real information-disclosure concern for HR data.

**The rule of thumb going forward:** this is a deliberate, scale-aware compromise between join performance and safe external identifiers — not a stylistic preference. Do not "simplify" a new model by picking one PK style for everything; apply the rule in §1.2 (URL/API-facing → add `public_id`; internal-only → skip it) on a per-model basis.

---

## 2. Foreign Key Conventions

- **Field name = the related model's snake_case name**, not `<x>_id`. Django appends `_id` to the actual DB column automatically, so `employee = models.ForeignKey(Employee, ...)` already produces an `employee_id` column — don't name the Python field `employee_id` yourself.
- **Always set `related_name` explicitly, and pluralize it.** Never rely on Django's default `<model>_set` — with several apps referencing the same models (`employees`, `compensation`, `attendance`, `organization`) implicit back-reference names collide in intent even when they don't collide in name, and explicit names make cross-app reverse lookups self-documenting.

```python
class EmployeeAssignmentHistory(CoreModel):
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="assignment_history",
    )
    restaurant = models.ForeignKey(
        "organization.Restaurant",
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    manager = models.ForeignKey(
        "employees.Employee",
        on_delete=models.PROTECT,
        related_name="direct_report_assignments",
        null=True,
        blank=True,
    )
```

---

## 3. Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Model names | `PascalCase`, singular | `EmployeeAssignmentHistory` |
| Field names | `snake_case` | `employee_number` |
| Boolean fields | prefixed `is_` / `has_` | `is_active`, `has_completed_onboarding` |
| Date-only fields | suffixed `_date` (`DateField`) | `effective_from`, `effective_to`, `hire_date` |
| Timestamp fields | suffixed `_at` (`DateTimeField`) | `created_at`, `updated_at`, `terminated_at` |
| Table names | Django default `<app_label>_<modelname>` | `employees_employee` — no custom `db_table` unless an app is renamed post-hoc and a stable table name must be preserved |

Note the precision distinction: `effective_from` / `effective_to` are `DateField` (effective-dating in this system is date-granularity — a transfer takes effect *on a day*, not at a specific second), while `created_at` / `updated_at` are `DateTimeField` (audit precision genuinely needs the timestamp). Don't mix these up when adding new effective-dated tables.

---

## 4. Indexing Strategy

Django gives every FK column an implicit index automatically — keep that, no action needed.

### 4.1 Composite indexes

Add composite indexes for the multi-column filters/sorts the app actually runs. Two concrete examples from this system:

```python
class EmployeeAssignmentHistory(CoreModel):
    class Meta:
        indexes = [
            # "Who is currently at restaurant X?"
            models.Index(fields=["restaurant", "effective_from"]),
            # "Show this employee's full history in order"
            models.Index(fields=["employee", "effective_from", "effective_to"]),
        ]
```

### 4.2 Partial indexes for "current record" lookups

The single most common query against every effective-dated table is "give me the current row." Indexing the entire history table for that is wasteful once history is years deep — instead, index only the open-ended rows:

```python
class EmployeeAssignmentHistory(CoreModel):
    class Meta:
        indexes = [
            models.Index(
                fields=["employee"],
                name="empassign_current_idx",
                condition=models.Q(effective_to__isnull=True),
            ),
        ]
```

This compiles to `CREATE INDEX ... WHERE effective_to IS NULL`. Since ~95% of "current state" queries only care about open-ended rows, this partial index stays small and fast even as the historical table grows into the millions.

### 4.3 Trigram search indexes

HR search screens (find an employee by name or employee number, fuzzy/partial match) need `icontains`-style search that scales. Enable `pg_trgm` and add GIN trigram indexes on the searched text columns:

```python
# migration
from django.contrib.postgres.operations import TrigramExtension


class Migration(migrations.Migration):
    operations = [
        TrigramExtension(),
    ]
```

```python
from django.contrib.postgres.indexes import GinIndex


class Person(CoreModel):
    class Meta:
        indexes = [
            GinIndex(fields=["full_name"], name="person_name_trgm_idx", opclasses=["gin_trgm_ops"]),
        ]


class Employee(CoreModel):
    class Meta:
        indexes = [
            GinIndex(
                fields=["employee_number"],
                name="employee_number_trgm_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ]
```

Without this, `Employee.objects.filter(person__full_name__icontains=query)` degrades to a sequential scan once the table is large. With the trigram index, Postgres can use it for `icontains`/`istartswith` and similarity search.

### 4.4 Unique constraints

- `employee_number` — unique across `Employee`.
- `public_id` — unique by virtue of the field definition itself (see §1.2).
- Effective-dating overlap uniqueness (e.g. "an employee cannot have two overlapping assignment periods") is enforced with a Postgres `ExclusionConstraint`, **not** a plain `unique_together`/`UniqueConstraint`, because the "no overlap" rule is a range condition, not an equality condition. This is covered in full in [`./data-lifecycle.md`](./data-lifecycle.md) — every effective-dated history table must implement the exclusion constraint documented there.

### 4.5 Check constraints

Check constraints are a last line of defense at the DB level, backing up (not replacing) validation done in forms/services:

```python
class EmployeeAssignmentHistory(CoreModel):
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="assignment_effective_to_after_from",
            ),
        ]


class SalaryHistory(CoreModel):
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gte=0),
                name="salary_amount_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="salary_effective_to_after_from",
            ),
        ]
```

Apply `effective_to IS NULL OR effective_to > effective_from` to **every** effective-dated table, and add sensible domain checks (non-negative amounts, valid enum ranges, etc.) wherever a bad value would otherwise silently corrupt reporting.

---

## 5. Nullable Field Policy

**Default to `NOT NULL` with a sensible default. Use `null=True` only when NULL has a genuinely distinct meaning from "empty" or "zero."**

- Text fields (`CharField`, `TextField`): **never** `null=True`. Use `blank=True` with the Django-conventional empty string as the "no value" state. Two representations of "nothing" (`NULL` and `""`) on the same column is a recurring source of bugs (`filter(field="")` silently missing NULL rows, etc.), so this project has exactly one.
- Non-string fields (dates, FKs, numbers, booleans-as-tri-state) may use `null=True` where "no value" is a real, distinct state:
  - `EmployeeAssignmentHistory.effective_to = models.DateField(null=True, blank=True)` — `NULL` deliberately means "open-ended / currently in effect," which is a meaningful state distinct from any actual date.
  - `CoreModel.created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)` — `NULL` means "no acting user recorded" (system/migration-created row), which is different from any real user.

```python
# Correct: text field, no null=True
notes = models.TextField(blank=True)

# Correct: date field, null is meaningful (open-ended)
effective_to = models.DateField(null=True, blank=True)

# Incorrect — do not do this
notes = models.TextField(null=True, blank=True)  # now "" and NULL both mean "no notes"
```

---

## 6. Soft Deletion Policy

**General rule: if a row's disappearance would break historical reportability or an audit trail, it is soft-deleted or never deleted at all. If it's disposable working data, hard delete is fine.**

Applied concretely:

| Category | Policy | Examples |
|---|---|---|
| People/employment records | **Never hard-deleted.** Termination is a status change plus an effective-dated assignment close, not a row deletion. | `Person`, `Employee` |
| Reference/lookup data | **Soft-delete** via `is_active` flag. Deactivating a restaurant must not orphan the historical assignments that point to it. | `Region`, `Area`, `Restaurant`, `Department`, `JobGrade` |
| Append-only transactional/log data | **No deletion concept at all.** Retained per the retention policy (see [`./data-lifecycle.md`](./data-lifecycle.md)), not "deleted" in the application sense. | `AuditLog`, `IntegrationLog` |
| Disposable working data | Hard delete is fine. | An abandoned draft recruitment application |

### 6.1 `SoftDeleteModel` mixin

Standard implementation, lives in `core`:

```python
# core/models.py
from django.db import models
from django.utils import timezone


class ActiveManager(models.Manager):
    """Default manager: excludes soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()  # default: active rows only
    all_objects = models.Manager()  # escape hatch: everything

    class Meta:
        abstract = True

    def deactivate(self):
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=["is_active", "deactivated_at"])

    def all_with_inactive(self):
        """Convenience accessor mirrored on managers used from instances/admin/audit views."""
        return type(self).all_objects.all()
```

Reference/lookup models inherit `SoftDeleteModel` in addition to the audit-fields base (see §7):

```python
class Restaurant(CoreModel, SoftDeleteModel):
    name = models.CharField(max_length=200)
    area = models.ForeignKey(
        "organization.Area", on_delete=models.PROTECT, related_name="restaurants"
    )
    ...
```

Admin and audit screens use `Restaurant.all_objects.all()` (or the `.all_with_inactive()` escape hatch) explicitly when inactive rows must be visible; every other code path gets active-only rows for free via the default manager.

---

## 7. Audit Fields

Nearly every model inherits a shared `core` base mixin providing four columns:

```python
# core/models.py
from django.conf import settings
from django.db import models


class CoreModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True
```

`created_by`/`updated_by` are nullable because system- and migration-created rows have no acting user to attribute the write to.

**This is deliberately separate from, and complementary to:**
- **django-simple-history** — tracks full field-level history (every value of every field, over time) for models that need it.
- **The custom `AuditLog`** (business-event log) — records meaningful business events ("Employee X's salary was changed by Y for reason Z"), not raw field diffs.

`created_at/updated_at/created_by/updated_by` answer only "who/when touched this row last." They're cheap, always present, and useful even on models that don't warrant full history tracking or business-event logging.

---

## 8. Cascade Policy

| `on_delete` | When to use | Example |
|---|---|---|
| `PROTECT` | **Default for FKs to reference/lookup data.** You must not be able to delete a `Restaurant`/`Department`/`JobGrade` that has historical rows pointing to it — deactivate it instead (§6). | `EmployeeAssignmentHistory.restaurant → Restaurant` |
| `CASCADE` | **Only for true parent-child composition**, where the child is meaningless without the parent. | `OnboardingTask.checklist → OnboardingChecklist` |
| `SET_NULL` | **Optional relational metadata** where losing the link is acceptable. Requires `null=True`. | `CoreModel.created_by → User` (if the acting user's account is later purged) |

```python
class Department(CoreModel, SoftDeleteModel): ...


class EmployeeAssignmentHistory(CoreModel):
    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.PROTECT,  # never delete a Department with history pointing to it
        related_name="assignments",
    )


class OnboardingTask(CoreModel):
    checklist = models.ForeignKey(
        "onboarding.OnboardingChecklist",
        on_delete=models.CASCADE,  # task has no independent meaning
        related_name="tasks",
    )


class SomeLogEntry(CoreModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
```

**Hard rule:** never use `CASCADE` from a lookup/reference table toward transactional/historical data. That direction is backwards — it would silently destroy history when someone deletes (rather than deactivates) a `Restaurant` or `Department`. If you find yourself reaching for `CASCADE` on an FK that points *away* from history *toward* a lookup table, it's the wrong choice; use `PROTECT`.

---

## 9. Transactions and Referential Integrity

- **Real foreign keys everywhere.** `ForeignKey(..., db_constraint=False)` is not used except for a deliberate, explicitly-justified cross-app decoupling case — and the app boundaries chosen for this project are not expected to need one. Referential integrity is enforced by Postgres, not just application code.
- **Every service function that performs more than one write wraps the writes in `transaction.atomic()`.** This applies especially to any operation that closes one effective-dated row while opening another (see [`./data-lifecycle.md`](./data-lifecycle.md) §"Transaction behavior") — the close-old/open-new pair must succeed or fail together.
- **`select_for_update()` for genuinely concurrency-sensitive paths.** Most of this system is low-concurrency HR data entry, so most service functions don't need row locking. The one clear exception: approving a leave request against a shared `LeaveBalance` — two concurrent approvals racing against the same balance must not both succeed. Lock the balance row for the duration of the atomic block:

```python
from django.db import transaction


def approve_leave_request(leave_request_id: int, approved_by):
    with transaction.atomic():
        leave_request = LeaveRequest.objects.select_related("employee").get(pk=leave_request_id)

        balance = LeaveBalance.objects.select_for_update().get(
            employee=leave_request.employee, leave_type=leave_request.leave_type
        )

        if balance.remaining_days < leave_request.requested_days:
            raise InsufficientLeaveBalanceError

        balance.remaining_days -= leave_request.requested_days
        balance.save(update_fields=["remaining_days"])

        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.approved_by = approved_by
        leave_request.save(update_fields=["status", "approved_by", "updated_at"])
```

`select_for_update()` takes a row-level lock on the `LeaveBalance` row for the transaction's duration, so a second concurrent approval attempting the same `select_for_update()` blocks until the first commits (or rolls back) — preventing a double-spend of leave balance.

---

## Summary checklist for a new model

1. Inherit `CoreModel` (audit fields) and, if it's reference/lookup data, `SoftDeleteModel`.
2. Add `public_id` only if the model is URL/API/user-facing.
3. Name FKs after the related model, always set an explicit pluralized `related_name`.
4. Pick `on_delete` per §8 — `PROTECT` is the default for anything pointing at reference data.
5. `null=True` only for non-string fields where NULL is a real, distinct state.
6. Add composite/partial/GIN indexes for the query patterns the feature actually needs.
7. Add check constraints for domain invariants; add an `ExclusionConstraint` if it's effective-dated (see [`./data-lifecycle.md`](./data-lifecycle.md)).
8. Wrap any multi-write service function in `transaction.atomic()`; add `select_for_update()` only where real concurrent-write races are possible.
