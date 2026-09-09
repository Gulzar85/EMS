import datetime as dt

import pytest

from apps.accounts.models import UserScope
from apps.accounts.tests.factories import UserFactory
from apps.employees import selectors
from apps.employees.services import EmployeeAssignmentService
from apps.employees.tests.factories import make_employee
from apps.organization.tests.factories import PositionFactory, make_area

pytestmark = pytest.mark.django_db


def _employee_with_position(position_kwargs=None, **employee_kwargs):
    employee = make_employee(**employee_kwargs)
    position = PositionFactory(status="active", **(position_kwargs or {}))
    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 1, 1),
        actor=None,
    )
    return employee


# --- Organization scoping (list) ------------------------------------------------


def test_superuser_sees_every_employee():
    superuser = UserFactory(is_superuser=True)
    _employee_with_position(position_kwargs={'department__location__organization_unit': make_area()})
    assert selectors.get_employees_for_list(superuser).count() >= 1


def test_user_with_no_scope_sees_no_employees():
    user = UserFactory()
    _employee_with_position(position_kwargs={'department__location__organization_unit': make_area()})
    assert selectors.get_employees_for_list(user).count() == 0


def test_organization_unit_scope_covers_only_its_subtree():
    from apps.organization.tests.factories import make_region

    region_a = make_region()
    area_a = make_area(region=region_a)
    employee_a = _employee_with_position(position_kwargs={'department__location__organization_unit': area_a})

    area_b = make_area()
    _employee_with_position(position_kwargs={'department__location__organization_unit': area_b})

    user = UserFactory()
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.ORGANIZATION_UNIT, organization_unit=region_a
    )

    visible = list(selectors.get_employees_for_list(user))
    assert visible == [employee_a]


def test_employee_with_no_current_position_is_invisible_to_org_unit_scoped_users():
    """An employee who's never been assigned a position (or is between
    assignments) has nothing for the org-scope OR-filter to match through
    — correctly invisible to an ORGANIZATION_UNIT-scoped viewer, though
    still visible to an unrestricted superuser or GLOBAL scope (those skip
    the field-path filter entirely, per `restrict_by_organization`)."""
    make_employee()  # no position assignment at all
    area_scoped_user = UserFactory()
    UserScope.objects.create(
        user=area_scoped_user,
        scope_type=UserScope.ScopeType.ORGANIZATION_UNIT,
        organization_unit=make_area(),
    )
    assert selectors.get_employees_for_list(area_scoped_user).count() == 0

    global_scoped_user = UserFactory()
    UserScope.objects.create(user=global_scoped_user, scope_type=UserScope.ScopeType.GLOBAL)
    assert selectors.get_employees_for_list(global_scoped_user).count() == 1

    superuser = UserFactory(is_superuser=True)
    assert selectors.get_employees_for_list(superuser).count() == 1


# --- Self-access widening at the detail level -----------------------------------


def test_user_with_no_org_scope_can_still_reach_their_own_employee_record():
    area = make_area()
    employee = _employee_with_position(position_kwargs={'department__location__organization_unit': area})
    user = UserFactory()
    employee.user = user
    employee.save()

    found = selectors.get_employee_by_public_id(employee.public_id, user)
    assert found == employee


def test_user_cannot_reach_another_employees_record_via_self_widening():
    area = make_area()
    employee = _employee_with_position(position_kwargs={'department__location__organization_unit': area})
    other_user = UserFactory()  # not linked to `employee`, no org scope either

    found = selectors.get_employee_by_public_id(employee.public_id, other_user)
    assert found is None


def test_get_my_profile_returns_the_linked_employee():
    user = UserFactory()
    employee = make_employee()
    employee.user = user
    employee.save()

    assert selectors.get_my_profile(user) == employee


def test_get_my_profile_returns_none_when_unlinked():
    user = UserFactory()
    assert selectors.get_my_profile(user) is None


# --- Subordinates / dashboard ----------------------------------------------------


def test_get_subordinates_returns_direct_reports_only():
    from apps.employees.services import EmployeeManagerService

    manager = make_employee()
    report = make_employee()
    other = make_employee()
    EmployeeManagerService.assign_manager(
        employee=report, manager=manager, start_date=dt.date(2024, 1, 1), actor=None
    )

    superuser = UserFactory(is_superuser=True)
    subordinates = list(selectors.get_subordinates(manager, superuser))
    assert subordinates == [report]
    assert other not in subordinates


def test_dashboard_metrics_counts_match_seed_expectations():
    superuser = UserFactory(is_superuser=True)
    area = make_area()
    _employee_with_position(position_kwargs={'department__location__organization_unit': area})
    _employee_with_position(position_kwargs={'department__location__organization_unit': area})

    metrics = selectors.get_employee_dashboard_metrics(superuser)
    assert metrics["total_employees"] == 2
    assert metrics["active_employees"] == 2
    assert sum(metrics["by_employment_type"].values()) == 2
