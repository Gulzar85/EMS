"""Object-level authorization for the employees app — reuses
`apps.organization.permissions.restrict_by_organization` directly rather
than re-implementing subtree resolution (Phase 04 brief §46 explicitly
asks to reuse the existing architecture, not scatter role checks).

`Employee` has no direct `organization_unit`/`location` field of its own
(Phase 04 brief §23) — scoping traverses through the denormalized
`current_position` pointer instead, which is exactly the field paths
`apps.organization.selectors._POSITION_UNIT_PATHS` already uses, prefixed
with `current_position__`.
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.organization.permissions import restrict_by_organization

EMPLOYEE_UNIT_PATHS = [
    "current_position__organization_unit_id",
    "current_position__department__organization_unit_id",
    "current_position__department__location__organization_unit_id",
]
EMPLOYEE_LOCATION_PATHS = ["current_position__department__location_id"]


def restrict_employees_by_organization(queryset: QuerySet, user) -> QuerySet:
    """List-scope restriction: an employee with no current position (never
    assigned, or between assignments) is invisible to every org-scoped
    viewer until assigned — visible only to a superuser/GLOBAL scope, or
    to themselves via `restrict_employees_for_detail`."""
    return restrict_by_organization(
        queryset,
        user,
        unit_field_paths=EMPLOYEE_UNIT_PATHS,
        location_field_paths=EMPLOYEE_LOCATION_PATHS,
    )


def restrict_employees_for_detail(queryset: QuerySet, user) -> QuerySet:
    """Object-level restriction for Detail/Update/History views: the same
    organization scoping as the list, WIDENED to always include the
    viewer's own employee record (Phase 04 brief §47's "My Profile" must
    work even for a user whose only access is to themselves — requiring a
    dedicated SELF `UserScope` row per user would be needless operational
    overhead for a check this direct)."""
    scoped = restrict_employees_by_organization(queryset, user)
    if not user.is_authenticated:
        return scoped
    # Both sides must carry the same `.distinct()` state before combining —
    # `restrict_by_organization` returns its OR-filtered branch already
    # `.distinct()`-flagged, but the unrestricted (superuser/GLOBAL) branch
    # isn't, and Django's QuerySet.__or__ refuses to combine a "unique"
    # query with a non-unique one (raises TypeError), which real test
    # coverage caught immediately.
    self_match = queryset.filter(user_id=user.id).distinct()
    return (scoped.distinct() | self_match).distinct()
