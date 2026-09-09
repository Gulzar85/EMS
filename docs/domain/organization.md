# Organization Domain

Status: **Implemented (Phase 03)**. See [ADR-016](../adr/ADR-016-organization-hierarchy.md) for the design rationale, [organization-architecture.md](../architecture/organization-architecture.md) for the technical architecture.

## The shape

```
Company
  └── OrganizationUnit (self-referential: Corporate → Region → Area, + BusinessUnit anywhere)
        └── Location (any physical facility — restaurant/office/warehouse/training center)
              └── Restaurant (operational profile, only when location_type = restaurant)
        └── Department (anchored to EITHER an OrganizationUnit OR a Location, never both)
              └── Department (sub-departments, via its own `parent`)
```

`Company` is a configurable root — never hardcode "McDonald's Pakistan" into application logic; it's seeded data (`seed_organization` management command), and the schema supports more than one company if this system is ever used for a different brand or entity.

`OrganizationUnit` is a pure structural tree (`unit_type ∈ {CORPORATE, REGION, AREA, BUSINESS_UNIT, OTHER}`) — it does **not** represent restaurants or departments directly (see ADR-016 for why). Parent-type validity is enforced (a Region's parent must be Corporate; an Area's parent must be Region) and circular parent chains are rejected, both in `OrganizationUnit.clean()` and re-validated at the form layer.

`Location` is any physical place. `Restaurant` is a `OneToOneField` profile of a `Location` carrying only restaurant-specific operational facts (`restaurant_number`, `operational_status`) — a restaurant's name, code, address, and geographic anchor all live on its `Location`, not duplicated onto `Restaurant`.

`Department` anchors to *either* an `OrganizationUnit` (a corporate/regional department, e.g. "Regional Finance") *or* a `Location` (a facility-level department, e.g. "Kitchen" at a specific restaurant) — enforced by a database `CheckConstraint`, not just application code. Departments have their own separate `parent` for sub-departments, independent of the geographic tree.

## What's deliberately NOT here yet

- **No `Employee` model** (Phase 04). Nothing in this domain references an employee directly.
- **No `Department.manager` field** — will be a FK to `Employee` once that model exists (see [position-management.md](position-management.md)).
- **No normalized Province/District/City reference tables** — `Location` stores these as plain indexed `CharField`s. This is a deliberate Phase 03 simplification, not an oversight: normalizing all of Pakistan's administrative divisions is real, separable scope that doesn't change this phase's core architectural questions. Adding reference tables later is additive (new FK fields alongside or replacing the CharFields), not a `Location` restructure.
- **No soft-delete flag on every model.** Master data (Restaurant, Department, Job, Position) uses `is_active`/`status` for deactivation, and hard deletion is restricted via `on_delete=PROTECT` wherever a row might already be referenced by history-bearing data — matching the existing project-wide database conventions, not a new pattern invented for this app.

## Authorization

Every organization-anchored model (`OrganizationUnit`, `Location`, `Restaurant`, `Department`, `Position`) is scope-restricted per user via `apps.organization.permissions` + `apps.accounts.models.UserScope` — see [ADR-018](../adr/ADR-018-organizational-access-scoping.md) for the full design. `JobFamily`/`JobLevel`/`Job` are **not** scope-restricted — they're global master data.

## Seed data

`python manage.py seed_organization` — idempotent, creates a realistic sample hierarchy (one Company, 2 regions, 3 areas, 10 restaurants across Lahore/Islamabad/Karachi, a few corporate business units, departments and positions per restaurant). No real employee data — there's nothing employee-shaped to seed yet. Safe to re-run.
