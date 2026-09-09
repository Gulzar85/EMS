"""Reusable read queries for the employees app. Every list/detail-shaped
selector is scope-restricted via apps.employees.permissions — CBVs never
fetch "everything" and filter in the template (matching the organization
app's own established pattern, Phase 03 plan §55).
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.employees.constants import CURRENTLY_EMPLOYED_STATUSES
from apps.employees.models import (
    Employee,
    EmployeeManagerAssignment,
    EmployeePositionAssignment,
)
from apps.employees.permissions import (
    restrict_employees_by_organization,
    restrict_employees_for_detail,
)
from apps.organization.models import Job

_LIST_RELATED = (
    "employment",
    "user",
    "current_position",
    "current_position__job",
    "current_position__department",
    "current_position__organization_unit",
    "current_manager",
)


def get_employees_for_list(
    user,
    q: str = "",
    status: str = "",
    employment_type: str = "",
    department: int | None = None,
    position: int | None = None,
    manager: int | None = None,
    organization_unit: int | None = None,
) -> QuerySet[Employee]:
    qs = Employee.objects.select_related(*_LIST_RELATED)
    qs = restrict_employees_by_organization(qs, user)
    if q:
        qs = qs.filter(
            Q(employee_number__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(preferred_name__icontains=q)
            | Q(contact__work_email__icontains=q)
            | Q(contact__mobile_number__icontains=q)
        )
    if status:
        qs = qs.filter(employment__status=status)
    if employment_type:
        qs = qs.filter(employment__employment_type=employment_type)
    if department:
        qs = qs.filter(current_position__department_id=department)
    if position:
        qs = qs.filter(current_position_id=position)
    if manager:
        qs = qs.filter(current_manager_id=manager)
    if organization_unit:
        qs = qs.filter(
            Q(current_position__organization_unit_id=organization_unit)
            | Q(current_position__department__organization_unit_id=organization_unit)
            | Q(current_position__department__location__organization_unit_id=organization_unit)
        )
    return qs.distinct()


def get_employee_by_public_id(public_id, user) -> Employee | None:
    qs = restrict_employees_for_detail(
        Employee.objects.select_related(*_LIST_RELATED), user
    )
    return qs.filter(public_id=public_id).first()


def get_employee_by_number(employee_number: str, user) -> Employee | None:
    qs = restrict_employees_for_detail(
        Employee.objects.select_related(*_LIST_RELATED), user
    )
    return qs.filter(employee_number=employee_number).first()


def get_my_profile(user) -> Employee | None:
    return Employee.objects.select_related(*_LIST_RELATED).filter(user_id=user.id).first()


def get_assignment_history(employee: Employee) -> QuerySet[EmployeePositionAssignment]:
    return employee.position_assignments.select_related(
        "position", "position__job", "position__department"
    ).order_by("-start_date")


def get_current_assignments(employee: Employee) -> QuerySet[EmployeePositionAssignment]:
    return get_assignment_history(employee).filter(end_date__isnull=True)


def get_manager_history(employee: Employee) -> QuerySet[EmployeeManagerAssignment]:
    return employee.manager_assignments.select_related("manager").order_by("-start_date")


def get_subordinates(employee: Employee, user) -> QuerySet[Employee]:
    qs = Employee.objects.select_related(*_LIST_RELATED).filter(current_manager=employee)
    return restrict_employees_by_organization(qs, user)


def get_active_employees(user) -> QuerySet[Employee]:
    return get_employees_for_list(user).filter(employment__status__in=CURRENTLY_EMPLOYED_STATUSES)


def get_new_joiners(user, since: dt.date) -> QuerySet[Employee]:
    return get_employees_for_list(user).filter(employment__joining_date__gte=since)


def get_employee_headcount(user) -> int:
    return get_active_employees(user).count()


def get_employee_dashboard_metrics(user) -> dict:
    today = timezone.localdate()
    thirty_days_ago = today - dt.timedelta(days=30)
    base = get_employees_for_list(user)

    # Counted in Python rather than `.values(...).annotate(Count(...))`: the
    # base queryset already carries `.distinct()` (from the org-scoping
    # `restrict_by_organization` OR-filter) plus several joins, and
    # `annotate()` over a `distinct()` + multi-join queryset is a well-known
    # Django footgun that silently mis-groups — verified against the seed
    # dataset while building this, where it undercounted every bucket.
    active = get_active_employees(user)
    employment_type_labels = dict(Job.EmploymentCategory.choices)
    by_type = Counter(
        employment_type_labels.get(value, value)
        for value in active.values_list("employment__employment_type", flat=True)
    )
    by_location = Counter(
        name
        for name in active.values_list(
            "current_position__department__location__name", flat=True
        )
        if name
    )

    return {
        "total_employees": base.count(),
        "active_employees": get_active_employees(user).count(),
        "inactive_employees": base.exclude(
            employment__status__in=CURRENTLY_EMPLOYED_STATUSES
        ).count(),
        "new_joiners_30d": get_new_joiners(user, thirty_days_ago).count(),
        "on_probation": base.filter(employment__status="probation").count(),
        "by_employment_type": dict(by_type),
        "by_location": dict(by_location),
    }
