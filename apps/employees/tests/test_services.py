import datetime as dt
import threading

import pytest
from django.db import connections

from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditLog
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.models import Employee, EmployeeEmployment
from apps.employees.services import (
    EmployeeAssignmentService,
    EmployeeLifecycleService,
    EmployeeManagerService,
    EmployeeNumberService,
    EmployeeService,
    EmployeeUserLinkService,
)
from apps.employees.tests.factories import make_employee
from apps.organization.models import Job
from apps.organization.tests.factories import PositionFactory

pytestmark = pytest.mark.django_db


# --- EmployeeNumberService --------------------------------------------------------


def test_employee_number_is_sequential_and_prefixed():
    first = EmployeeNumberService.generate()
    second = EmployeeNumberService.generate()
    assert first.startswith("EMP-")
    assert int(second.split("-")[1]) == int(first.split("-")[1]) + 1


def test_employee_number_never_derived_from_primary_key():
    employee = EmployeeService.create_employee(
        actor=None,
        first_name="Test",
        last_name="Employee",
        joining_date=dt.date(2024, 1, 1),
        employment_type=Job.EmploymentCategory.FULL_TIME,
    )
    assert employee.employee_number != str(employee.pk)
    assert employee.employee_number.startswith("EMP-")


@pytest.mark.django_db(transaction=True)
def test_employee_number_generation_is_concurrency_safe():
    """Uses `transaction=True` (real commits across threads, each on its
    own DB connection) rather than the default rolled-back-transaction
    test isolation, which would hide cross-connection row locking
    behavior entirely."""
    results: list[str] = []
    errors: list[Exception] = []

    def _generate():
        try:
            results.append(EmployeeNumberService.generate())
        except Exception as exc:  # noqa: BLE001 — capturing for the assertion below
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=_generate) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(results) == len(set(results)) == 10  # every generated number is unique


# --- EmployeeService ---------------------------------------------------------------


def test_create_employee_creates_all_three_rows_atomically():
    employee = EmployeeService.create_employee(
        actor=None,
        first_name="Ali",
        last_name="Raza",
        work_email="ali.raza@mcdonalds.com.pk",
        joining_date=dt.date(2024, 1, 1),
        employment_type=Job.EmploymentCategory.FULL_TIME,
    )
    assert Employee.objects.filter(pk=employee.pk).exists()
    assert employee.contact.work_email == "ali.raza@mcdonalds.com.pk"
    assert employee.employment.status == EmployeeEmployment.Status.DRAFT
    assert AuditLog.objects.filter(action="employee.created").exists()


def test_update_employee_updates_contact_fields():
    employee = make_employee()
    updated = EmployeeService.update_employee(
        employee=employee, actor=None, first_name="Updated", mobile_number="03001112222"
    )
    updated.refresh_from_db()
    assert updated.first_name == "Updated"
    assert updated.contact.mobile_number == "03001112222"


def test_update_employee_cannot_touch_employment_status():
    """Employment status changes only through EmployeeLifecycleService —
    update_employee silently ignores any `status`/`employment_type` kwarg
    that isn't in its recognized field sets (Phase 04 brief §27, §91)."""
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    EmployeeService.update_employee(employee=employee, actor=None, status="terminated")
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.ACTIVE


# --- EmployeeLifecycleService -------------------------------------------------------


def test_activate_draft_employee_without_probation_goes_straight_to_active():
    employee = make_employee(status=EmployeeEmployment.Status.DRAFT, probation_end_date=None)
    EmployeeLifecycleService.activate(employee=employee, actor=None)
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.ACTIVE


def test_activate_draft_employee_with_probation_end_date_goes_to_probation():
    employee = make_employee(
        status=EmployeeEmployment.Status.DRAFT, probation_end_date=dt.date(2024, 4, 1)
    )
    EmployeeLifecycleService.activate(employee=employee, actor=None)
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.PROBATION


def test_activate_already_active_employee_rejected():
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    with pytest.raises(EmployeeValidationError):
        EmployeeLifecycleService.activate(employee=employee, actor=None)


def test_confirm_sets_confirmation_date_and_activates():
    employee = make_employee(status=EmployeeEmployment.Status.PROBATION)
    EmployeeLifecycleService.confirm(employee=employee, actor=None)
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.ACTIVE
    assert employee.employment.confirmation_date is not None


def test_confirm_requires_probation_status():
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    with pytest.raises(EmployeeValidationError):
        EmployeeLifecycleService.confirm(employee=employee, actor=None)


def test_place_on_leave_and_return_cycle():
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    EmployeeLifecycleService.place_on_leave(employee=employee, actor=None)
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.ON_LEAVE

    EmployeeLifecycleService.return_from_leave(employee=employee, actor=None)
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.ACTIVE


def test_suspend_requires_active_status():
    employee = make_employee(status=EmployeeEmployment.Status.DRAFT)
    with pytest.raises(EmployeeValidationError):
        EmployeeLifecycleService.suspend(employee=employee, actor=None)


def test_suspend_and_reinstate_cycle():
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    EmployeeLifecycleService.suspend(employee=employee, actor=None)
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.SUSPENDED

    EmployeeLifecycleService.reinstate(employee=employee, actor=None)
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.ACTIVE


def test_deactivate_sets_termination_fields():
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    EmployeeLifecycleService.deactivate(
        employee=employee,
        status=EmployeeEmployment.Status.RESIGNED,
        reason="Better opportunity",
        effective_date=dt.date(2024, 6, 1),
        actor=None,
    )
    employee.employment.refresh_from_db()
    assert employee.employment.status == EmployeeEmployment.Status.RESIGNED
    assert employee.employment.termination_date == dt.date(2024, 6, 1)
    assert employee.employment.termination_reason == "Better opportunity"


def test_deactivate_rejects_non_terminal_target_status():
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    with pytest.raises(EmployeeValidationError):
        EmployeeLifecycleService.deactivate(
            employee=employee, status=EmployeeEmployment.Status.ON_LEAVE, reason="x", actor=None
        )


def test_deactivate_already_terminated_employee_rejected():
    employee = make_employee(status=EmployeeEmployment.Status.TERMINATED)
    with pytest.raises(EmployeeValidationError):
        EmployeeLifecycleService.deactivate(
            employee=employee,
            status=EmployeeEmployment.Status.RESIGNED,
            reason="x",
            actor=None,
        )


# --- EmployeeAssignmentService -------------------------------------------------------


def test_assign_primary_position_syncs_current_position():
    employee = make_employee()
    position = PositionFactory(status="active")

    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 1, 1),
        actor=None,
    )

    employee.refresh_from_db()
    assert employee.current_position_id == position.id


def test_assigning_a_new_primary_position_ends_the_previous_one():
    employee = make_employee()
    first_position = PositionFactory(status="active")
    second_position = PositionFactory(status="active")

    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=first_position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 1, 1),
        actor=None,
    )
    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=second_position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 6, 1),
        actor=None,
    )

    employee.refresh_from_db()
    assert employee.current_position_id == second_position.id
    first_assignment = employee.position_assignments.get(position=first_position)
    assert first_assignment.end_date == dt.date(2024, 6, 1)
    assert employee.position_assignments.filter(is_primary=True, end_date__isnull=True).count() == 1


def test_secondary_assignment_does_not_touch_current_position():
    employee = make_employee()
    primary_position = PositionFactory(status="active")
    secondary_position = PositionFactory(status="active")

    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=primary_position,
        assignment_type="primary",
        is_primary=True,
        start_date=dt.date(2024, 1, 1),
        actor=None,
    )
    EmployeeAssignmentService.assign_position(
        employee=employee,
        position=secondary_position,
        assignment_type="acting",
        is_primary=False,
        start_date=dt.date(2024, 2, 1),
        actor=None,
    )

    employee.refresh_from_db()
    assert employee.current_position_id == primary_position.id


def test_end_assignment_clears_current_position_when_it_was_primary():
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

    EmployeeAssignmentService.end_assignment(
        assignment=assignment, end_date=dt.date(2024, 12, 1), actor=None
    )

    employee.refresh_from_db()
    assert employee.current_position is None


def test_end_already_ended_assignment_rejected():
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
    EmployeeAssignmentService.end_assignment(assignment=assignment, actor=None)

    with pytest.raises(EmployeeValidationError):
        EmployeeAssignmentService.end_assignment(assignment=assignment, actor=None)


# --- EmployeeManagerService -------------------------------------------------------


def test_assign_manager_syncs_current_manager():
    employee = make_employee()
    manager = make_employee()

    EmployeeManagerService.assign_manager(
        employee=employee, manager=manager, start_date=dt.date(2024, 1, 1), actor=None
    )

    employee.refresh_from_db()
    assert employee.current_manager_id == manager.id


def test_assigning_a_new_manager_ends_the_previous_assignment():
    employee = make_employee()
    old_manager = make_employee()
    new_manager = make_employee()

    EmployeeManagerService.assign_manager(
        employee=employee, manager=old_manager, start_date=dt.date(2024, 1, 1), actor=None
    )
    EmployeeManagerService.assign_manager(
        employee=employee, manager=new_manager, start_date=dt.date(2024, 6, 1), actor=None
    )

    employee.refresh_from_db()
    assert employee.current_manager_id == new_manager.id
    old_assignment = employee.manager_assignments.get(manager=old_manager)
    assert old_assignment.end_date == dt.date(2024, 6, 1)


def test_assign_manager_rejects_self_management():
    employee = make_employee()
    with pytest.raises(EmployeeValidationError):
        EmployeeManagerService.assign_manager(
            employee=employee, manager=employee, start_date=dt.date(2024, 1, 1), actor=None
        )


def test_end_manager_assignment_clears_current_manager():
    employee = make_employee()
    manager = make_employee()
    assignment = EmployeeManagerService.assign_manager(
        employee=employee, manager=manager, start_date=dt.date(2024, 1, 1), actor=None
    )

    EmployeeManagerService.end_manager_assignment(assignment=assignment, actor=None)

    employee.refresh_from_db()
    assert employee.current_manager is None


# --- EmployeeUserLinkService -------------------------------------------------------


def test_link_user_sets_the_relationship():
    employee = make_employee()
    user = UserFactory()
    EmployeeUserLinkService.link_user(employee=employee, user=user, actor=None)
    employee.refresh_from_db()
    assert employee.user_id == user.id
    assert AuditLog.objects.filter(action="employee.user_linked").exists()


def test_link_user_rejects_already_linked_employee():
    employee = make_employee()
    user_a = UserFactory()
    user_b = UserFactory()
    EmployeeUserLinkService.link_user(employee=employee, user=user_a, actor=None)
    with pytest.raises(EmployeeValidationError):
        EmployeeUserLinkService.link_user(employee=employee, user=user_b, actor=None)


def test_link_user_rejects_user_already_linked_to_another_employee():
    user = UserFactory()
    other_employee = make_employee()
    EmployeeUserLinkService.link_user(employee=other_employee, user=user, actor=None)

    employee = make_employee()
    with pytest.raises(EmployeeValidationError):
        EmployeeUserLinkService.link_user(employee=employee, user=user, actor=None)


def test_unlink_user_clears_the_relationship():
    employee = make_employee()
    user = UserFactory()
    EmployeeUserLinkService.link_user(employee=employee, user=user, actor=None)

    EmployeeUserLinkService.unlink_user(employee=employee, actor=None)

    employee.refresh_from_db()
    assert employee.user_id is None


def test_unlink_user_requires_existing_link():
    employee = make_employee()
    with pytest.raises(EmployeeValidationError):
        EmployeeUserLinkService.unlink_user(employee=employee, actor=None)
