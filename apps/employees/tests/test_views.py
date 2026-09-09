import datetime as dt

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.models import UserScope
from apps.accounts.tests.factories import UserFactory
from apps.employees.models import Employee, EmployeeEmployment
from apps.employees.services import (
    EmployeeAssignmentService,
    EmployeeManagerService,
)
from apps.employees.tests.factories import make_employee
from apps.organization.models import Job
from apps.organization.tests.factories import PositionFactory, make_area, make_region

pytestmark = pytest.mark.django_db


def _permissioned_user(*codenames):
    user = UserFactory()
    perms = Permission.objects.filter(content_type__app_label="employees", codename__in=codenames)
    user.user_permissions.add(*perms)
    UserScope.objects.create(user=user, scope_type=UserScope.ScopeType.GLOBAL)
    return user


def _employee_in(area):
    employee = make_employee()
    position = PositionFactory(status="active", department__location__organization_unit=area)
    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 1, 1),
        actor=None,
    )
    return employee


# --- Dashboard ---------------------------------------------------------------


def test_dashboard_redirects_anonymous_to_login(client):
    response = client.get(reverse("employees:dashboard"))
    assert response.status_code == 302


def test_dashboard_forbidden_without_permission(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get(reverse("employees:dashboard"))
    assert response.status_code == 403


def test_dashboard_ok_with_permission(client):
    user = _permissioned_user("view_employee")
    client.force_login(user)
    response = client.get(reverse("employees:dashboard"))
    assert response.status_code == 200
    assert "metrics" in response.context


# --- Employee list -------------------------------------------------------------


def test_employee_list_htmx_returns_partial(client):
    user = _permissioned_user("view_employee")
    client.force_login(user)
    _employee_in(make_area())

    response = client.get(reverse("employees:employee-list"), headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert b"<html" not in response.content.lower()


# --- IDOR / object-level scoping -------------------------------------------------


def test_scoped_out_user_gets_404_on_direct_detail_url(client):
    region_a = make_region()
    area_a = make_area(region=region_a)
    employee = _employee_in(area_a)

    other_area = make_area()
    user = UserFactory()
    perms = Permission.objects.filter(content_type__app_label="employees", codename="view_employee")
    user.user_permissions.add(*perms)
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.ORGANIZATION_UNIT, organization_unit=other_area
    )
    client.force_login(user)

    response = client.get(
        reverse("employees:employee-detail", kwargs={"public_id": employee.public_id})
    )

    assert response.status_code == 404


def test_scoped_user_can_access_their_own_employee(client):
    area = make_area()
    employee = _employee_in(area)
    user = UserFactory()
    perms = Permission.objects.filter(content_type__app_label="employees", codename="view_employee")
    user.user_permissions.add(*perms)
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.ORGANIZATION_UNIT, organization_unit=area
    )
    client.force_login(user)

    response = client.get(
        reverse("employees:employee-detail", kwargs={"public_id": employee.public_id})
    )

    assert response.status_code == 200


def test_user_with_no_permission_can_still_reach_their_own_profile_via_my_profile(client):
    """A crew member with zero `employees` permissions must still be able
    to see their own profile — MyProfileView is deliberately not
    permission-gated the way the roster/detail views are (Phase 04 brief
    §47)."""
    user = UserFactory()
    employee = make_employee()
    employee.user = user
    employee.save()
    client.force_login(user)

    response = client.get(reverse("employees:my-profile"))

    assert response.status_code == 200
    assert response.context["employee"] == employee


def test_my_profile_404_when_no_employee_linked(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get(reverse("employees:my-profile"))
    assert response.status_code == 404


# --- Create / Update / Delete ----------------------------------------------------


def test_employee_create_via_post(client):
    user = _permissioned_user("add_employee")
    client.force_login(user)

    response = client.post(
        reverse("employees:employee-create"),
        {
            "first_name": "New",
            "last_name": "Hire",
            "joining_date": "2024-01-01",
            "employment_type": Job.EmploymentCategory.FULL_TIME,
        },
    )

    assert response.status_code == 302
    assert Employee.objects.filter(first_name="New", last_name="Hire").exists()


def test_employee_update_via_post(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee(first_name="Old")

    response = client.post(
        reverse("employees:employee-update", kwargs={"public_id": employee.public_id}),
        {
            "first_name": "New",
            "last_name": employee.last_name,
        },
    )

    assert response.status_code == 302
    employee.refresh_from_db()
    assert employee.first_name == "New"


def test_employee_delete_get_never_mutates(client):
    user = _permissioned_user("view_employee", "delete_employee")
    client.force_login(user)
    employee = make_employee(status=EmployeeEmployment.Status.DRAFT)

    client.get(reverse("employees:employee-delete", kwargs={"public_id": employee.public_id}))

    assert Employee.objects.filter(pk=employee.pk).exists()


def test_draft_employee_can_be_deleted(client):
    user = _permissioned_user("view_employee", "delete_employee")
    client.force_login(user)
    employee = make_employee(status=EmployeeEmployment.Status.DRAFT)

    response = client.post(
        reverse("employees:employee-delete", kwargs={"public_id": employee.public_id})
    )

    assert response.status_code == 302
    assert not Employee.objects.filter(pk=employee.pk).exists()


def test_active_employee_cannot_be_deleted(client):
    """Only DRAFT employees are reachable via the delete URL's scoped
    queryset (Phase 04 brief §36) — an ACTIVE employee's delete URL
    behaves like the object doesn't exist, not a 403."""
    user = _permissioned_user("view_employee", "delete_employee")
    client.force_login(user)
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)

    response = client.get(
        reverse("employees:employee-delete", kwargs={"public_id": employee.public_id})
    )

    assert response.status_code == 404


# --- Lifecycle -------------------------------------------------------------------


def test_activate_via_post(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee(status=EmployeeEmployment.Status.DRAFT)

    response = client.post(
        reverse("employees:employee-activate", kwargs={"public_id": employee.public_id}),
        {"reason": ""},
    )

    assert response.status_code == 302
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.ACTIVE


def test_lifecycle_action_requires_change_permission(client):
    user = _permissioned_user("view_employee")  # no change_employee
    client.force_login(user)
    employee = make_employee(status=EmployeeEmployment.Status.DRAFT)

    response = client.post(
        reverse("employees:employee-activate", kwargs={"public_id": employee.public_id}), {}
    )

    assert response.status_code == 403


def test_activate_already_active_shows_error_not_crash(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)

    response = client.post(
        reverse("employees:employee-activate", kwargs={"public_id": employee.public_id}),
        {"reason": ""},
    )

    assert response.status_code == 302  # redirected back with an error message, not a 500


def test_deactivate_via_post_sets_terminal_status(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)

    response = client.post(
        reverse("employees:employee-deactivate", kwargs={"public_id": employee.public_id}),
        {
            "status": EmployeeEmployment.Status.RESIGNED,
            "effective_date": "2024-06-01",
            "reason": "Moving on",
        },
    )

    assert response.status_code == 302
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.RESIGNED


# --- Assignment / manager --------------------------------------------------------


def test_assignment_update_changes_primary_position(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee()
    old_position = PositionFactory(status="active")
    new_position = PositionFactory(status="active")
    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=old_position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 1, 1),
        actor=None,
    )

    response = client.post(
        reverse("employees:employee-assignment-update", kwargs={"public_id": employee.public_id}),
        {"position": new_position.pk, "start_date": "2024-06-01", "reason": ""},
    )

    assert response.status_code == 302
    employee.refresh_from_db()
    assert employee.current_position_id == new_position.id


def test_manager_assignment_cycle_shows_error_not_crash(client):
    """A ValidationError raised deep inside model.full_clean() (not the
    domain EmployeeValidationError) must still surface as a friendly
    redirect-with-message, not a 500 — this is exactly the class of bug
    the FBV->CBV ErrorView regression taught this project to test for."""
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee_a = make_employee()
    employee_b = make_employee()
    EmployeeManagerService.assign_manager(
        employee=employee_b, manager=employee_a, start_date=dt.date(2024, 1, 1), actor=None
    )

    response = client.post(
        reverse("employees:employee-manager-assignment", kwargs={"public_id": employee_a.public_id}),
        {"manager": employee_b.pk, "relationship_type": "direct", "start_date": "2024-06-01"},
    )

    assert response.status_code == 302  # redirected back with an error message, not a 500
    employee_a.refresh_from_db()
    assert employee_a.current_manager is None  # the cyclic change was rejected


def test_assignment_end_via_post(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee()
    position = PositionFactory(status="active")
    assignment = EmployeeAssignmentService.assign_position(
        employee=employee,
        position=position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 1, 1),
        actor=None,
    )

    response = client.post(
        reverse(
            "employees:employee-assignment-end",
            kwargs={"public_id": employee.public_id, "assignment_id": assignment.pk},
        ),
        {"end_date": "2024-06-01", "reason": ""},
    )

    assert response.status_code == 302
    employee.refresh_from_db()
    assert employee.current_position is None


# --- User linking ------------------------------------------------------------------


def test_link_user_via_post(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee()
    account_to_link = UserFactory()

    response = client.post(
        reverse("employees:employee-user-link", kwargs={"public_id": employee.public_id}),
        {"user": account_to_link.pk},
    )

    assert response.status_code == 302
    employee.refresh_from_db()
    assert employee.user_id == account_to_link.id


def test_unlink_user_via_post(client):
    user = _permissioned_user("view_employee", "change_employee")
    client.force_login(user)
    employee = make_employee()
    account = UserFactory()
    employee.user = account
    employee.save()

    response = client.post(
        reverse("employees:employee-user-unlink", kwargs={"public_id": employee.public_id}), {}
    )

    assert response.status_code == 302
    employee.refresh_from_db()
    assert employee.user_id is None


# --- History ------------------------------------------------------------------------


def test_history_view_ok_with_permission(client):
    user = _permissioned_user("view_employee")
    client.force_login(user)
    employee = make_employee()

    response = client.get(
        reverse("employees:employee-history", kwargs={"public_id": employee.public_id})
    )

    assert response.status_code == 200
    assert "assignment_history" in response.context
