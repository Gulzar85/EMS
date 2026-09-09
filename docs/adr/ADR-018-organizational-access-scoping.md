# ADR-018: Organizational Access Scoping (UserScope)

## Status
Accepted

## Context

Phase 03 §54 requires object-level authorization matching the organizational hierarchy — Regional HR should see their region's data, an Area Manager their area's, without scattering `if request.user.role == "..."` checks through every view. Phase 01 anticipated this and deliberately deferred building it, documenting: *"UserScope arrives with the organization app"* — the prerequisite (an actual organization hierarchy to scope against) didn't exist until now.

## Decision

`UserScope` (`apps/accounts/models.py`, not `apps/organization` — it's a reusable authorization primitive future apps, e.g. Employee/Leave, will also consume) with `scope_type ∈ {GLOBAL, ORGANIZATION_UNIT, LOCATION, SELF}`. A user may hold several scope rows. An `ORGANIZATION_UNIT` scope covers that unit's entire subtree (a Regional HR user scoped to "Region North" automatically sees every Area and Restaurant beneath it) — resolved by `apps/organization/permissions.py:get_descendant_unit_ids()`, a plain in-memory BFS over `(id, parent_id)` pairs cached in Django's cache framework for 5 minutes, invalidated explicitly on any `OrganizationUnit` write (`invalidate_unit_tree_cache()`, called from `services.create_organization_unit`/`update_organization_unit`).

Every organization selector (`apps/organization/selectors.py`) routes list/detail querysets through `restrict_by_unit()`/`restrict_by_location()`, which return the queryset unmodified for superusers or a `GLOBAL` scope, and otherwise filter to accessible ids — this is the single centralized enforcement point CBVs rely on, rather than each view re-implementing scope logic. Detail/Update/Delete views additionally scope their `get_queryset()` the same way, so a scoped-out user hitting a direct URL for an object outside their scope gets a plain 404 (the object isn't in their queryset) rather than a 403 that would confirm the object's existence.

`JobFamily`/`JobLevel`/`Job` are deliberately **not** scoped — they're global master data, not anchored to any part of the organizational tree.

## Alternatives Considered

- **`django-guardian`** (per-object permission grants) — rejected (same reasoning as Phase 00's original authorization ADR): guardian's per-object model doesn't naturally express "everything under this Area" without granting to every individual Restaurant row.
- **`django-mptt`/`django-treebeard`** for subtree resolution — rejected as an unjustified dependency at this scale (a few hundred organization units, not tens of thousands); a plain BFS over a cached parent map is simpler and fast enough.
- **Scattering `if request.user.region == ...` checks in each view** — exactly what §54 explicitly warns against; rejected outright.
- **A real-time recursive SQL CTE per request** instead of a cached in-memory map — rejected as unnecessary complexity for a dataset this small; the cache is invalidated on every write, so staleness is bounded to worst-case "wrote-then-read-within-cache-window by a different request," acceptable for this domain (org restructuring is rare and not security-critical to the second).

## Consequences

**Positive**: one centralized, testable scoping mechanism reused by every future app that needs organization-anchored access control; no per-view authorization logic to audit individually.

**Negative**: `UserScope` rows must be seeded/assigned per user (no UI for this yet in Phase 03 — an admin task via Django admin or a future management command) for scoping to actually restrict anyone; a user with zero scope rows and `is_superuser=False` sees nothing, which is correct but must be understood by whoever provisions accounts. Cache invalidation is coarse (the whole tree, not just the affected subtree) — acceptable given how infrequently the tree structure changes and how small it is to rebuild.
