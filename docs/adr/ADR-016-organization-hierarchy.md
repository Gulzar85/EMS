# ADR-016: Organization Hierarchy — OrganizationUnit as a Pure Structural Tree

## Status
Accepted

## Context

Phase 03 needed to model McDonald's Pakistan's organizational structure: Company → Region → Area → Restaurant → Department. The brief's own starting suggestion was a single generic, self-referential `OrganizationUnit` model with a `unit_type` choice field covering every level, including `Restaurant` and `Department` as possible types.

Restaurant and Department both need substantial fields that don't belong on a generic tree node: a restaurant needs address/geo/contact/operational-status fields (§14-16 of the brief); a department needs a manager (deferred) and its own sub-department hierarchy independent of the geographic tree. Giving every restaurant both a "thin" `OrganizationUnit` row (for tree position) and a "rich" `Restaurant`/`Location` profile row (for its actual data) is two rows tracking one real-world thing, kept in sync for no benefit.

## Decision

`OrganizationUnit` is a **pure structural tree** covering only the administrative/geographic/functional levels that have no rich attributes of their own: `CORPORATE`, `REGION`, `AREA`, `BUSINESS_UNIT` (corporate support functions — HR/Finance/IT — that sit in the tree without being a physical facility), and `OTHER` (escape hatch). `Restaurant` and `Department` are **not** unit types.

Physical facilities are modeled as a `Location` (any facility — restaurant/office/warehouse/training center) with an `organization_unit` FK anchoring it into the tree (typically under an `AREA`), and `Restaurant` is a `OneToOneField` profile of `Location` carrying only restaurant-specific operational facts (restaurant_number, operational_status). `Department` anchors to *either* an `OrganizationUnit` (corporate/regional department) *or* a `Location` (facility-level department) via a database `CheckConstraint`, with its own separate self-referential `parent` for sub-departments — a different hierarchy axis from the geographic tree entirely.

Parent-type validity is enforced by an explicit `ALLOWED_PARENT_TYPES` map checked in `OrganizationUnit.clean()` (Region's parent must be Corporate; Area's parent must be Region; BusinessUnit may sit under Corporate, Region, or Area), plus cycle prevention via a shared `assert_no_cycle()` helper (`apps/organization/validators.py`) reused by `OrganizationUnit.parent`, `Department.parent`, and `Position.reports_to`.

## Alternatives Considered

- **Everything as one `OrganizationUnit` type, including Restaurant/Department** (the brief's literal starting suggestion) — rejected: forces a redundant thin/rich row pair per restaurant, and Department's dual anchor (organization_unit or location) becomes impossible to express cleanly if Department is itself just another `OrganizationUnit` row.
- **A fully generic tree using `django-mptt`/`django-treebeard`** — rejected as an unjustified dependency: the tree stays a few hundred rows (regions/areas/business units), a plain adjacency-list self-FK with a cached in-memory BFS (see ADR-018) is simpler and sufficient at this scale.
- **Merging Location and Restaurant into one table** — rejected: future facility types (a `TrainingCenter` profile, say) would force nullable restaurant-only columns onto every non-restaurant location row.

## Consequences

**Positive**: each model carries only the fields relevant to what it represents; no redundant bookkeeping; the tree stays small and fast to traverse; Department's real-world dual nature (facility-level vs. corporate-level) is expressible without contortion.

**Negative**: three different models (`OrganizationUnit`, `Location`, `Restaurant`) must be understood together to answer "where does this restaurant sit in the org chart" — a `Restaurant.location.organization_unit` chain, not a single lookup. Documented clearly in `docs/domain/organization.md` so this isn't a surprise to future engineers.
