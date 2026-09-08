# Audit

> Part of the security architecture package. See [security-architecture.md](../architecture/security-architecture.md) for the high-level narrative tying this document together with [authentication.md](./authentication.md) and [authorization.md](./authorization.md).

## 1. Why Hybrid

Two distinct questions come up when someone asks "what happened to this record":

1. *"What fields changed on this specific row, when, and to what value?"* — a field-level diff question, useful for debugging and for reconstructing a record's history.
2. *"What business event happened, why, and who approved it?"* — an event-level question, useful for compliance, HR investigations, and answering "who terminated this employee and why" without wading through raw field diffs.

A single mechanism does not answer both well. Automatic field-level history logs every field change including incidental ones (e.g. a `updated_at` bump, a cache-invalidation touch) and has no place to record *why* something changed. A hand-written event log is precise about business meaning but is easy to under-instrument (someone forgets to log an edge case) if it's the *only* audit mechanism. EMS uses both.

## 2. `django-simple-history` — Field-Level History

`django-simple-history`'s `HistoricalRecords()` manager is attached directly to sensitive/historical models:

- `Employee`
- `EmployeeAssignmentHistory`
- `SalaryHistory` (in `compensation`)
- `UserScope` (and other permission-assignment models)
- `ThemeConfiguration`

This gives, with minimal per-model code, an automatically-maintained shadow history table per model: every save produces a historical row capturing the full field state at that point, who made the change (via simple-history's user-tracking middleware), and when. It is queryable per-instance (`employee.history.all()`) for "show me this record's timeline" views, and requires no service-layer code to keep working — it hooks Django's model save signal, so it can't be forgotten by a future developer adding a new field.

This layer is **not** where business-event semantics or a "reason" field live — it is a mechanical, complete record of field states over time, one row per save.

## 3. Custom `audit` App — Business-Event Log

The `audit` app owns an `AuditLog` model for business-EVENT-level entries — one row per meaningful action, not one row per field touched. Approving a leave request is one event even though it may update `LeaveRequest.status` and `LeaveBalance.remaining_days` in the same transaction; `AuditLog` records that as a single `leave.approved` entry, while `django-simple-history` separately captures the two individual field diffs on their respective models.

### 3.1 `AuditLog` Fields

| Field | Type / Notes |
|---|---|
| `actor` | FK to `User`, **nullable** for system-initiated actions (e.g. a scheduled job) |
| `timestamp` | When the event was recorded (set at write time, inside the same transaction as the business change) |
| `action` | Verb string, e.g. `"employee.transferred"`, `"leave.approved"`, `"document.verified"`, `"permission.granted"`, `"theme.updated"` |
| `entity_type` | Generic reference to the affected model (e.g. `"employees.Employee"`) |
| `entity_id` | The entity's `public_id` (never the internal numeric PK — keeps audit rows stable across any PK renumbering and avoids leaking sequential internal IDs) |
| `previous_value` | JSON snapshot of the *relevant* fields before the change (not the whole row) |
| `new_value` | JSON snapshot of the *relevant* fields after the change |
| `reason` | Free text; **required** (enforced at the service layer) for sensitive actions such as termination or salary change |
| `ip_address` | Source IP of the request that triggered the action |
| `correlation_id` | Ties the entry to the triggering HTTP request's correlation ID (set by `core` middleware), so a support engineer can trace one request across application logs and audit entries |

`previous_value`/`new_value` are deliberately scoped snapshots (e.g. `{"status": "PENDING"}` → `{"status": "APPROVED"}`), not a full-row dump — this keeps entries readable and avoids duplicating what `django-simple-history` already stores field-by-field on models that have it attached.

### 3.2 Tamper Resistance

- **Insert-only at the application/permission level:** no Django group — including System Admin — is granted the `change` or `delete` permission on `AuditLog` via the standard admin site; the admin registration for `AuditLog` should expose add/view only (and in practice, adds happen exclusively through service code, never through the admin UI).
- **Database-level hardening (Recommended, Phase 01 DBA setup):** `REVOKE UPDATE, DELETE ON audit_auditlog FROM <app_db_role>` at the PostgreSQL level, so that even a compromised application credential or a bug in application code cannot alter or remove existing audit rows — only `INSERT` remains possible for the app's own database role.
- Both controls are complementary: the Django-permission control stops normal application misuse; the DB-level `REVOKE` stops anything that bypasses the ORM (raw SQL, a compromised credential, a careless data-fix script).

### 3.3 Transaction Boundary Rule

**The audit write must commit or roll back atomically with the business change it describes — it is never a best-effort, after-the-fact write.** Concretely:

```python
# apps/compensation/services.py
from django.db import transaction


def change_salary(*, user, employee, new_salary, reason, ip_address, correlation_id):
    policies.assert_can_change_salary(user, employee)
    with transaction.atomic():
        old_salary = employee.compensation.base_salary
        employee.compensation.base_salary = new_salary
        employee.compensation.save()  # also creates a SalaryHistory row via simple-history

        AuditLog.objects.create(
            actor=user,
            action="compensation.salary_changed",
            entity_type="employees.Employee",
            entity_id=employee.public_id,
            previous_value={"base_salary": str(old_salary)},
            new_value={"base_salary": str(new_salary)},
            reason=reason,  # required for this action type
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
        # transaction.on_commit is NOT used for the AuditLog write above —
        # it must land in the same commit as the salary change, not best-effort after.

        transaction.on_commit(
            lambda: notify_salary_change.delay(
                employee.public_id
            )  # fire-and-forget email/notification
        )
```

`transaction.on_commit()` is the right tool for triggering a notification or email about the change — that side effect can safely be fire-and-forget and lose nothing important if it fails. It is explicitly **not** the right tool for the `AuditLog` write itself: if the business change succeeds but the audit write is only attempted after commit and then fails (process crash, DB blip), the system would have a salary change with no audit trail of it — an unacceptable gap for HR/compliance-sensitive events. Writing the audit row inside the same `atomic()` block guarantees the two either both persist or both roll back together.

## 4. Required Audit Coverage — Action-to-Service Mapping

| Business action (from brief) | Service function | `AuditLog.action` value |
|---|---|---|
| Employee creation | `employees.services.create_employee()` | `employee.created` |
| Employee modification | `employees.services.update_employee()` | `employee.updated` |
| Position change | `employees.services.change_position()` | `employee.position_changed` |
| Restaurant transfer | `employees.services.transfer_employee()` | `employee.transferred` |
| Manager change | `employees.services.change_manager()` | `employee.manager_changed` |
| Promotion | `employees.services.promote_employee()` | `employee.promoted` |
| Salary change | `compensation.services.change_salary()` | `compensation.salary_changed` |
| Leave approval | `leave.services.approve_leave()` | `leave.approved` |
| Termination | `employees.services.terminate_employee()` | `employee.terminated` |
| Document verification | `documents.services.verify_document()` | `document.verified` |
| Permission changes | `accounts.services.grant_permission()` / `revoke_permission()` (covers Group membership and `UserScope` grants) | `permission.granted` / `permission.revoked` |
| Theme changes | `theme.services.update_theme()` | `theme.updated` |
| Configuration changes | `core.services.update_configuration()` | `configuration.updated` |

Each of the above service functions is the single place its action can be triggered from (per the layering contract in [system-architecture.md](../architecture/system-architecture.md)) — there is no direct-write path that bypasses the service and therefore no path that skips the audit entry.

## 5. Who Can View the Audit Log

Audit data is itself sensitive (it can reveal salary history, disciplinary actions, and who-accessed-what) and is therefore **scope-filtered like every other read in the system**, following the same selector pattern described in [authorization.md](./authorization.md):

- **HR Security/Compliance role and System Admin** — the only roles intended to browse audit history broadly, subject to their own `UserScope` (e.g. a regional HR Compliance officer sees audit entries for their region, not globally, unless granted `GLOBAL` scope).
- **An Area Manager (or any operational manager role) does not get audit-browsing access at all**, and even where a narrow audit view is exposed to them in the future (e.g. "history of this one leave request"), it would be scoped to entities they already have `view_*` permission and scope coverage for — never a general audit log browser.
- Per-instance history (`django-simple-history`'s `.history.all()`) surfaced inline on a record's detail page is gated by that record's own view permission/scope — no separate grant needed, since it's just "this record's timeline," not the audit log.

**The dedicated audit-log viewer UI (search, filter by actor/action/date range, export) is a Phase 1+ build item.** Phase 00 defines the `AuditLog` model, the write path, and the access rule above; it does not build the browsing interface.

## 6. What This Document Does Not Cover

- Retention periods for audit/historical data — addressed in `../database/data-lifecycle.md` (cross-referenced, not duplicated here; see [security-architecture.md](../architecture/security-architecture.md#4-data-privacy--pii-handling) for the pointer).
- The distinction between audit log content (restricted-access, old/new values) and general application logs (must never contain sensitive field values) — see [security-architecture.md](../architecture/security-architecture.md#4-data-privacy--pii-handling).
- Authorization mechanics used to scope-filter audit queries — see [authorization.md](./authorization.md).
