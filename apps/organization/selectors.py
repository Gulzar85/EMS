"""Reusable read queries for the organization app. Every list-shaped
selector is scope-restricted via apps.organization.permissions — CBVs
never fetch "everything" and filter in the template (Phase 03 plan §55).

JobFamily/JobLevel/Job are global master data (a "Crew Member" job isn't
tied to one restaurant), so they are NOT scope-restricted — only the
organization-hierarchy-anchored models are (Location/Restaurant/
Department/Position/OrganizationUnit itself).
"""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet, Sum

from apps.organization.models import (
    Department,
    Job,
    JobFamily,
    JobLevel,
    Location,
    OrganizationUnit,
    Position,
    Restaurant,
)
from apps.organization.permissions import (
    get_accessible_unit_ids,
    restrict_by_organization,
    restrict_by_unit,
)

# --- OrganizationUnit ---------------------------------------------------


def get_organization_units_for_list(user, q: str = "") -> QuerySet[OrganizationUnit]:
    qs = OrganizationUnit.objects.select_related("parent", "company").order_by("sort_order", "name")
    qs = restrict_by_unit(qs, user, field_paths=["id"])
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return qs


def get_root_units_for_user(user) -> QuerySet[OrganizationUnit]:
    """Top-level nodes visible to `user` — the true root(s) if
    unrestricted, else the topmost node(s) of their accessible subtree."""
    accessible = get_accessible_unit_ids(user)
    if accessible is None:
        return OrganizationUnit.objects.filter(parent__isnull=True, is_active=True).order_by(
            "sort_order", "name"
        )
    qs = OrganizationUnit.objects.filter(id__in=accessible, is_active=True)
    return qs.filter(Q(parent__isnull=True) | ~Q(parent_id__in=accessible)).order_by(
        "sort_order", "name"
    )


def get_child_units(parent_id, user) -> QuerySet[OrganizationUnit]:
    qs = OrganizationUnit.objects.filter(parent_id=parent_id, is_active=True).order_by(
        "sort_order", "name"
    )
    accessible = get_accessible_unit_ids(user)
    if accessible is not None:
        qs = qs.filter(id__in=accessible)
    return qs


# --- Location / Restaurant ------------------------------------------------


def get_locations_for_list(user, q: str = "") -> QuerySet[Location]:
    qs = Location.objects.select_related("organization_unit").order_by("name")
    qs = restrict_by_organization(
        qs, user, unit_field_paths=["organization_unit_id"], location_field_paths=["id"]
    )
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return qs


def get_active_locations(user) -> QuerySet[Location]:
    return get_locations_for_list(user).filter(is_active=True)


def get_restaurants_for_list(
    user, q: str = "", status: str = "", location_type: str = ""
) -> QuerySet[Restaurant]:
    qs = Restaurant.objects.select_related("location", "location__organization_unit").order_by(
        "restaurant_number"
    )
    qs = restrict_by_organization(
        qs,
        user,
        unit_field_paths=["location__organization_unit_id"],
        location_field_paths=["location_id"],
    )
    if q:
        qs = qs.filter(
            Q(location__name__icontains=q)
            | Q(restaurant_number__icontains=q)
            | Q(location__code__icontains=q)
        )
    if status:
        qs = qs.filter(operational_status=status)
    if location_type:
        qs = qs.filter(location__location_type=location_type)
    return qs


def get_active_restaurants(user) -> QuerySet[Restaurant]:
    return get_restaurants_for_list(user).filter(
        operational_status=Restaurant.OperationalStatus.OPERATING
    )


# --- Department -----------------------------------------------------------


def get_departments_for_list(user, q: str = "") -> QuerySet[Department]:
    qs = Department.objects.select_related("organization_unit", "location", "parent").order_by(
        "name"
    )
    qs = restrict_by_organization(
        qs,
        user,
        unit_field_paths=["organization_unit_id", "location__organization_unit_id"],
        location_field_paths=["location_id"],
    )
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return qs


def get_department_positions(department: Department) -> QuerySet[Position]:
    return department.positions.select_related("job").order_by("code")


# --- Job master data (global, not scope-restricted) ------------------------


def get_job_families_for_list(q: str = "") -> QuerySet[JobFamily]:
    qs = JobFamily.objects.order_by("name")
    return qs.filter(Q(name__icontains=q) | Q(code__icontains=q)) if q else qs


def get_job_levels_for_list(q: str = "") -> QuerySet[JobLevel]:
    qs = JobLevel.objects.order_by("rank")
    return qs.filter(Q(name__icontains=q) | Q(code__icontains=q)) if q else qs


def get_jobs_for_list(
    q: str = "", job_family: int | None = None, job_level: int | None = None
) -> QuerySet[Job]:
    qs = Job.objects.select_related("job_family", "job_level").order_by("title")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(code__icontains=q))
    if job_family:
        qs = qs.filter(job_family_id=job_family)
    if job_level:
        qs = qs.filter(job_level_id=job_level)
    return qs


# --- Position ---------------------------------------------------------------

_POSITION_UNIT_PATHS = [
    "organization_unit_id",
    "department__organization_unit_id",
    "department__location__organization_unit_id",
]


def get_positions_for_list(
    user,
    q: str = "",
    status: str = "",
    job_family: int | None = None,
    department: int | None = None,
) -> QuerySet[Position]:
    qs = Position.objects.select_related(
        "job", "job__job_family", "department", "organization_unit"
    ).order_by("code")
    qs = restrict_by_organization(
        qs,
        user,
        unit_field_paths=_POSITION_UNIT_PATHS,
        location_field_paths=["department__location_id"],
    )
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(code__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if job_family:
        qs = qs.filter(job__job_family_id=job_family)
    if department:
        qs = qs.filter(department_id=department)
    return qs


def get_vacant_positions(user) -> QuerySet[Position]:
    # headcount_limit stands in for vacant_headcount today — occupied_headcount
    # is always 0 until Phase 04's EmployeeAssignment exists (see Position
    # model docstring / ADR-019).
    return get_positions_for_list(user).filter(status=Position.Status.ACTIVE, headcount_limit__gt=0)


def get_position_headcount_summary(user) -> dict:
    aggregate = get_positions_for_list(user, status=Position.Status.ACTIVE).aggregate(
        authorized=Sum("headcount_limit"), count=Count("id")
    )
    authorized = aggregate["authorized"] or 0
    occupied = 0  # Phase 04 seam — see Position.occupied_headcount
    vacant = authorized - occupied
    return {
        "authorized_headcount": authorized,
        "occupied_headcount": occupied,
        "vacant_headcount": vacant,
        "vacancy_rate": round(vacant / authorized * 100, 1) if authorized else 0.0,
        "active_position_count": aggregate["count"] or 0,
    }


# --- Dashboard ---------------------------------------------------------------


def get_organization_dashboard_metrics(user) -> dict:
    return {
        "total_units": get_organization_units_for_list(user).count(),
        "active_locations": get_active_locations(user).count(),
        "active_restaurants": get_active_restaurants(user).count(),
        "active_departments": get_departments_for_list(user).filter(is_active=True).count(),
        "active_jobs": Job.objects.filter(is_active=True).count(),
        **get_position_headcount_summary(user),
    }
