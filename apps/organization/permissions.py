"""Centralized object-level authorization for the organization domain —
the strategy Phase 03 plan §54 asks for in place of scattered
`if user.role == ...` checks, consuming `apps.accounts.models.UserScope`.

Subtree resolution is a plain in-memory BFS over cached (id, parent_id)
pairs — not django-mptt/django-treebeard, an unjustified dependency at
McDonald's Pakistan's actual scale (a few hundred organization units, not
tens of thousands). See Phase 03 plan judgment call #8.
"""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Q, QuerySet

_UNIT_TREE_CACHE_KEY = "organization:unit_parent_map"
_UNIT_TREE_CACHE_TIMEOUT = 300  # 5 min — cheap to rebuild, short TTL keeps it fresh after edits


def _get_children_map() -> dict[int | None, list[int]]:
    cached = cache.get(_UNIT_TREE_CACHE_KEY)
    if cached is not None:
        return cached

    from apps.organization.models import OrganizationUnit

    children_map: dict[int | None, list[int]] = {}
    for unit_id, parent_id in OrganizationUnit.objects.values_list("id", "parent_id"):
        children_map.setdefault(parent_id, []).append(unit_id)
    cache.set(_UNIT_TREE_CACHE_KEY, children_map, _UNIT_TREE_CACHE_TIMEOUT)
    return children_map


def invalidate_unit_tree_cache() -> None:
    cache.delete(_UNIT_TREE_CACHE_KEY)


def get_descendant_unit_ids(root_id: int) -> set[int]:
    """`root_id` itself plus every descendant unit id."""
    children_map = _get_children_map()
    result = {root_id}
    queue = [root_id]
    while queue:
        current = queue.pop()
        for child_id in children_map.get(current, []):
            if child_id not in result:
                result.add(child_id)
                queue.append(child_id)
    return result


def get_accessible_unit_ids(user) -> set[int] | None:
    """The set of OrganizationUnit ids `user` may see. `None` means
    unrestricted (superuser, or an explicit GLOBAL scope) — callers must
    check for `None` before treating an empty set as "sees nothing."
    """
    from apps.accounts.models import UserScope

    if user.is_superuser:
        return None

    scopes = list(user.scopes.all())
    if any(s.scope_type == UserScope.ScopeType.GLOBAL for s in scopes):
        return None

    unit_ids: set[int] = set()
    for scope in scopes:
        if scope.scope_type == UserScope.ScopeType.ORGANIZATION_UNIT and scope.organization_unit_id:
            unit_ids |= get_descendant_unit_ids(scope.organization_unit_id)
    return unit_ids


def get_accessible_location_ids(user) -> set[int] | None:
    """`None` means unrestricted. Otherwise: explicit LOCATION scopes plus
    every location whose organization_unit falls under an accessible
    ORGANIZATION_UNIT scope.
    """
    from apps.accounts.models import UserScope
    from apps.organization.models import Location

    if user.is_superuser:
        return None

    scopes = list(user.scopes.all())
    if any(s.scope_type == UserScope.ScopeType.GLOBAL for s in scopes):
        return None

    location_ids = {
        s.location_id
        for s in scopes
        if s.scope_type == UserScope.ScopeType.LOCATION and s.location_id
    }

    unit_ids = get_accessible_unit_ids(user)
    if unit_ids is None:
        return None
    if unit_ids:
        location_ids |= set(
            Location.objects.filter(organization_unit_id__in=unit_ids).values_list("id", flat=True)
        )
    return location_ids


def restrict_by_unit(queryset: QuerySet, user, *, field_paths: list[str]) -> QuerySet:
    """Restrict `queryset` to rows reachable, via ANY of `field_paths`
    (dotted lookups to an OrganizationUnit id, e.g. "organization_unit_id"
    or "department__organization_unit_id"), from an accessible unit.
    """
    accessible = get_accessible_unit_ids(user)
    if accessible is None:
        return queryset

    query = Q()
    for path in field_paths:
        query |= Q(**{f"{path}__in": accessible})
    return queryset.filter(query).distinct()


def restrict_by_location(queryset: QuerySet, user, *, field_paths: list[str]) -> QuerySet:
    """Same as restrict_by_unit, but for models reachable via a Location id
    (e.g. "location_id" on Restaurant, "location__id" chains elsewhere)."""
    accessible = get_accessible_location_ids(user)
    if accessible is None:
        return queryset

    query = Q()
    for path in field_paths:
        query |= Q(**{f"{path}__in": accessible})
    return queryset.filter(query).distinct()


def restrict_by_organization(
    queryset: QuerySet,
    user,
    *,
    unit_field_paths: list[str] = (),
    location_field_paths: list[str] = (),
) -> QuerySet:
    """Restrict via EITHER an accessible-unit path OR an accessible-location
    path — a user may hold an ORGANIZATION_UNIT scope, a standalone LOCATION
    scope, or both at once (e.g. a Restaurant Manager granted direct access
    to one specific restaurant outside their normal area). Location/
    Restaurant/Department/Position selectors use this rather than
    `restrict_by_unit` alone, so a LOCATION-only scope isn't silently
    ignored (a real bug caught by apps/organization/tests/test_selectors.py
    while building this).
    """
    accessible_units = get_accessible_unit_ids(user)
    accessible_locations = get_accessible_location_ids(user)
    if accessible_units is None or accessible_locations is None:
        return queryset  # superuser or a GLOBAL scope

    query = Q()
    for path in unit_field_paths:
        query |= Q(**{f"{path}__in": accessible_units})
    for path in location_field_paths:
        query |= Q(**{f"{path}__in": accessible_locations})
    if not unit_field_paths and not location_field_paths:
        return queryset.none()
    return queryset.filter(query).distinct()
