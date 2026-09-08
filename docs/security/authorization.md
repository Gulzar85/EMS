# Authorization

> Part of the security architecture package. See [security-architecture.md](../architecture/security-architecture.md) for the high-level narrative tying this document together with [authentication.md](./authentication.md) and [audit.md](./audit.md).

## 1. Why Not Simple Role Checks

A single flag or attribute check — `user.is_staff`, `user.role == "HR"`, `if request.user.is_manager` — cannot express what this system actually needs: **who** can see **what data**, scoped to **where in the org** that data sits. A Restaurant Manager and a Regional Manager might both hold something like "HR Generalist" capabilities in a naive role model, but one should see one restaurant's employees and the other should see every restaurant in their region — and neither should see salary figures unless a *separate* grant says so. EMS therefore combines two independent layers rather than one flat role field.

## 2. Layer 1 — Django Groups & Permissions (What)

Standard Django `Group`/`Permission` objects express **coarse capability**, independent of organizational placement:

- `employees.view_employee`, `employees.change_employee`
- `compensation.view_compensation`, `compensation.change_compensation`
- `leave.approve_leaverequest`
- `documents.view_document`
- `theme.manage_theme`
- ...and equivalent `view_*`/`change_*`/`approve_*` permissions per app.

Recommended baseline Groups: **HR Generalist, Restaurant Manager, Area Manager, Regional Manager, Payroll Officer, Trainer, Employee Self-Service, System Admin.** A `User` is assigned to one or more Groups; Groups are assigned permissions. This layer answers *"is this class of action available to this kind of user at all?"* — it says nothing about *which* employees, restaurants, or records the permission applies to.

## 3. Layer 2 — `UserScope` (Where)

A custom model expresses the organizational reach of a permission:

```python
class UserScope(models.Model):
    class ScopeType(models.TextChoices):
        GLOBAL = "GLOBAL"
        REGION = "REGION"
        AREA = "AREA"
        RESTAURANT = "RESTAURANT"
        DEPARTMENT = "DEPARTMENT"
        SELF = "SELF"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scopes"
    )
    scope_type = models.CharField(max_length=20, choices=ScopeType.choices)
    scope_id = models.CharField(
        max_length=64, null=True, blank=True
    )  # public_id of Region/Area/Restaurant/Department; null for GLOBAL/SELF
```

A user can hold **multiple** `UserScope` rows. Examples:

- An Area Manager holds one `AREA`-scoped row covering the area they manage — this single row covers every restaurant nested under that area, with no need to enumerate them.
- A Regional Manager holds one `REGION`-scoped row.
- Every authenticated employee implicitly has a `SELF` scope over their own employee record, for self-service actions (viewing their own leave balance, their own profile) — this does not require a database row; it is derived from `request.user`'s linked `Employee` record.
- A Payroll Officer might hold `GLOBAL` scope for `compensation` purposes while holding no scope at all for, say, `documents`.

Scope answers *"given the user has the permission, does it reach this particular entity?"*

## 4. Combining the Layers: `policies.py`

Each app that guards sensitive data exposes a `policies.py` module — the single place authorization logic for that domain lives. A policy function takes the acting user and the target entity and returns a boolean, combining: (a) does the user hold the relevant Django permission, and (b) does at least one of the user's scopes cover the target's org placement (or is the target the user's own record for `SELF`-scoped actions).

```python
# apps/employees/policies.py


def can_view_employee(user: User, employee: Employee) -> bool:
    """HR/managers with view_employee whose scope covers this employee's restaurant,
    or the employee viewing their own record."""
    if employee.user_id == user.id:
        return True
    if not user.has_perm("employees.view_employee"):
        return False
    return scope_covers_restaurant(user, employee.restaurant_id)


def can_edit_employee_profile(user: User, employee: Employee) -> bool:
    """change_employee permission, scope-checked, excluding compensation fields."""
    if not user.has_perm("employees.change_employee"):
        return False
    return scope_covers_restaurant(user, employee.restaurant_id)
```

```python
# apps/compensation/policies.py


def can_view_compensation(user: User, employee: Employee) -> bool:
    """Deliberately NOT implied by can_view_employee. Requires the separate
    compensation.view_compensation permission, typically granted only to
    HR/Payroll groups, still scope-filtered."""
    if not user.has_perm("compensation.view_compensation"):
        return False
    return scope_covers_restaurant(user, employee.restaurant_id)


def can_change_salary(user: User, employee: Employee) -> bool:
    if not user.has_perm("compensation.change_compensation"):
        return False
    return scope_covers_restaurant(user, employee.restaurant_id)
```

```python
# apps/leave/policies.py


def can_approve_leave(user: User, leave_request: LeaveRequest) -> bool:
    """Manager-chain approval: approve_leaverequest permission, scope covering
    the requester's restaurant/department, and the approver is not the requester."""
    if leave_request.employee.user_id == user.id:
        return False
    if not user.has_perm("leave.approve_leaverequest"):
        return False
    return scope_covers_restaurant(user, leave_request.employee.restaurant_id)


def can_view_leave_balance(user: User, employee: Employee) -> bool:
    if employee.user_id == user.id:
        return True
    if not user.has_perm("leave.view_leaverequest"):
        return False
    return scope_covers_restaurant(user, employee.restaurant_id)
```

`scope_covers_restaurant(user, restaurant_id)` (in `apps/core` or `apps/orgstructure`) resolves a restaurant's parent Area/Region and checks whether any of the user's `UserScope` rows cover it at `GLOBAL`, `REGION`, `AREA`, or `RESTAURANT` level — this hierarchy-resolution logic is written once and shared by every app's `policies.py`.

## 5. Canonical Worked Example: Restaurant Manager Sees Employees, Not Salaries

This is the example that motivates the whole two-layer design, spelled out end to end.

1. **Setup:** A Restaurant Manager, Ali, is assigned to the `Restaurant Manager` Django Group, which has the `employees.view_employee` permission but **not** `compensation.view_compensation`. Ali holds one `UserScope` row: `scope_type=RESTAURANT`, `scope_id=<his restaurant's public_id>`.
2. **Ali opens the employee list for his restaurant.** The view calls `employees.selectors.get_employees_for_user(ali)`. The selector filters `Employee.objects.filter(restaurant__in=restaurants_visible_to(ali))` — because Ali's only scope is `RESTAURANT`-level for his own restaurant, `restaurants_visible_to(ali)` resolves to exactly that one restaurant. Ali sees his restaurant's staff and nothing from any other restaurant, without the view ever writing restaurant-filtering logic itself.
3. **The employee list template renders name, position, and status** — fields that come from the `employees` app. It does **not** render salary, because the `employees` selector never selected or returned a compensation field in the first place; there is no salary column to accidentally leak.
4. **If Ali tries to view compensation directly** (e.g. by guessing a `/compensation/<employee_id>/` URL), the `compensation` view calls `compensation.policies.can_view_compensation(ali, employee)`. This checks `ali.has_perm("compensation.view_compensation")` — which is **false**, because that permission was never granted to the Restaurant Manager group. The view returns `403 Forbidden` regardless of Ali's `RESTAURANT` scope being otherwise valid for that employee.
5. **Why this can't be "fixed" by just checking `view_employee` harder:** `view_compensation` is architected as a wholly separate Django permission, living in a separate `compensation` app with its own selectors, services, templates, and URLs. There is no code path where an `employees` view — which only ever checks `view_employee` — can incidentally return compensation data, because compensation data does not live in any queryset or template that `employees` code touches. Even if HR/Payroll grants Ali `view_compensation` in the future, he would still only see compensation for employees within a scope he holds — the permission and the scope checks are independent and both must pass.

## 6. Enforcement Points: Defense in Depth

Authorization is checked at four points. This is deliberate redundancy, not accidental duplication — each layer closes a different failure mode.

| Layer | What it does | Why it exists |
|---|---|---|
| **(a) Selectors** | Every read queryset is scope-filtered at the source, e.g. `get_employees_for_user(user)` never returns rows outside the caller's scope. | A view can never "forget" to filter — the unsafe (unfiltered) query simply does not exist as an option. This is the layer that actually protects data if a view-level check is ever missing or wrong. |
| **(b) Services** | Every write calls the relevant `policies.py` function before mutating anything, inside the same transaction as the write. | Protects against writes reaching the database through *any* caller — a view, a management command, a future API endpoint, a Celery task — not just the one view that happens to call it today. |
| **(c) Views** | Check page-level Django permissions before even attempting to call the selector/service. | Fast, cheap `403` and clean UX (don't build a page just to discover the user can't see it) — this is a UX/performance optimization layered on top of (a)/(b), not the source of truth for security. |
| **(d) Templates** | Never contain authorization logic. At most, a template hides a button because the view already decided not to pass a permitted action into the context. | Keeps a single source of truth. A template check like `{% if user.role == 'HR' %}` is exactly the anti-pattern this architecture avoids — it duplicates logic that will drift from the real policy, and it enforces nothing (the underlying URL/service is still reachable directly). Real enforcement is always server-side in (a) and (b). |

The ordering matters: (a) and (b) are the actual security boundary — they must be correct on their own, with no assumption that (c) already filtered anything. (c) and (d) exist purely for usability and defense-in-depth, so that a bug in a view's early-exit logic does not become a data leak (the selector/service underneath still enforces the real rule).

## 7. `django-guardian` Evaluation — Rejected for Phase 00

[`django-guardian`](https://django-guardian.readthedocs.io/) was evaluated as an off-the-shelf alternative to the hand-rolled `UserScope` model, since it is a well-known, actively maintained Django object-permission library.

**How it works:** guardian grants permissions per individual object instance (row-level ACLs) — e.g. "user X has `view_employee` on Employee row #123."

**Why it was rejected:** EMS's access model is fundamentally **hierarchy-shaped**, not object-shaped. An Area Manager needs access to "everything under Area 7" — potentially dozens of restaurants and hundreds of employee rows, growing over time as restaurants and staff are added. Expressing that in guardian would mean granting a per-object row to every individual Restaurant and every individual Employee under that area, and re-granting on every new hire, transfer, or restaurant opening. That is an ongoing operational and maintenance burden that scales with data volume, for a pattern (org-hierarchy containment) that a small, purpose-built `UserScope` hierarchy expresses in one row per manager. `django-guardian` is the right tool when access genuinely varies per individual object with no shared structure (e.g. "share this specific document with these three named people"); it is the wrong tool for "manage everything under this node of the org tree."

**Revisit condition:** if a genuinely per-object (not per-hierarchy-node) exception pattern emerges later — e.g. "grant this one HR business partner visibility into this one specific employee outside their normal scope, as a one-off case" — that is a plausible future use for guardian (or a lightweight custom per-object override table) layered *alongside* `UserScope`, not a replacement for it. Not needed for Phase 00.

## 8. What This Document Does Not Cover

- How a user's identity is established before any of these checks run: see [authentication.md](./authentication.md).
- What gets recorded when a permission or scope grant itself changes (`permission.granted`, `UserScope` created/modified): see [audit.md](./audit.md).
- Per-data-category default visibility (Personal Info, Salary, Disciplinary, etc.): see [security-architecture.md](../architecture/security-architecture.md#4-data-privacy--pii-handling).
