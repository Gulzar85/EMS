import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.employees.models import (
    EmployeeEmployment,
    EmployeeManagerAssignment,
    EmployeePositionAssignment,
)
from apps.employees.tests.factories import (
    EmergencyContactFactory,
    EmployeeContactFactory,
    EmployeeEmploymentFactory,
    EmployeeFactory,
    EmployeeManagerAssignmentFactory,
    EmployeePositionAssignmentFactory,
    make_employee,
)
from apps.organization.tests.factories import PositionFactory

pytestmark = pytest.mark.django_db


# --- Employee identity -------------------------------------------------------


def test_display_name_prefers_preferred_name():
    employee = EmployeeFactory(first_name="Ahmed", last_name="Khan", preferred_name="Addy")
    assert employee.display_name == "Addy"


def test_display_name_falls_back_to_full_name():
    employee = EmployeeFactory(first_name="Ahmed", last_name="Khan", preferred_name="")
    assert employee.display_name == "Ahmed Khan"


def test_is_active_reflects_employment_status_not_a_stored_field():
    employee = make_employee(status=EmployeeEmployment.Status.ACTIVE)
    assert employee.is_active is True

    employee.employment.status = EmployeeEmployment.Status.TERMINATED
    employee.employment.save()
    employee.refresh_from_db()
    assert employee.is_active is False


def test_is_active_false_for_draft():
    employee = make_employee(status=EmployeeEmployment.Status.DRAFT)
    assert employee.is_active is False


# --- EmployeeContact -----------------------------------------------------------


def test_personal_email_is_not_unique():
    """Phase 04 brief §58 — personal emails can be legitimately shared."""
    EmployeeContactFactory(personal_email="shared@example.com")
    EmployeeContactFactory(personal_email="shared@example.com")  # must not raise


def test_work_email_is_unique_when_set():
    EmployeeContactFactory(work_email="unique@mcdonalds.com.pk")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmployeeContactFactory(work_email="unique@mcdonalds.com.pk")


def test_blank_work_email_allowed_for_multiple_employees():
    EmployeeContactFactory(work_email="")
    EmployeeContactFactory(work_email="")  # must not raise — partial unique constraint


# --- EmployeeEmployment ---------------------------------------------------------


def test_termination_date_before_joining_date_rejected():
    employment = EmployeeEmploymentFactory.build(
        joining_date=dt.date(2024, 1, 1), termination_date=dt.date(2023, 1, 1)
    )
    employment.employee = EmployeeFactory()
    with pytest.raises(ValidationError):
        employment.full_clean()


def test_probation_end_date_before_joining_date_rejected():
    employment = EmployeeEmploymentFactory.build(
        joining_date=dt.date(2024, 1, 1), probation_end_date=dt.date(2023, 1, 1)
    )
    employment.employee = EmployeeFactory()
    with pytest.raises(ValidationError):
        employment.full_clean()


def test_valid_employment_dates_pass_clean():
    employment = EmployeeEmploymentFactory.build(
        joining_date=dt.date(2024, 1, 1),
        probation_end_date=dt.date(2024, 4, 1),
        termination_date=None,
    )
    employment.employee = EmployeeFactory()
    employment.full_clean()  # must not raise


# --- EmergencyContact ------------------------------------------------------------


def test_multiple_emergency_contacts_allowed():
    employee = EmployeeFactory()
    EmergencyContactFactory(employee=employee)
    EmergencyContactFactory(employee=employee)
    assert employee.emergency_contacts.count() == 2


def test_only_one_primary_emergency_contact_per_employee():
    employee = EmployeeFactory()
    EmergencyContactFactory(employee=employee, is_primary=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmergencyContactFactory(employee=employee, is_primary=True)


def test_two_non_primary_emergency_contacts_allowed():
    employee = EmployeeFactory()
    EmergencyContactFactory(employee=employee, is_primary=False)
    EmergencyContactFactory(employee=employee, is_primary=False)  # must not raise


# --- EmployeePositionAssignment --------------------------------------------------


def test_only_one_active_primary_position_assignment_per_employee():
    employee = EmployeeFactory()
    EmployeePositionAssignmentFactory(employee=employee, is_primary=True, end_date=None)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmployeePositionAssignmentFactory(employee=employee, is_primary=True, end_date=None)


def test_a_second_primary_assignment_is_allowed_once_the_first_has_ended():
    employee = EmployeeFactory()
    EmployeePositionAssignmentFactory(
        employee=employee, is_primary=True, end_date=dt.date(2024, 6, 1)
    )
    EmployeePositionAssignmentFactory(
        employee=employee, is_primary=True, end_date=None
    )  # must not raise


def test_secondary_assignments_do_not_collide_with_primary_uniqueness():
    employee = EmployeeFactory()
    EmployeePositionAssignmentFactory(employee=employee, is_primary=True, end_date=None)
    EmployeePositionAssignmentFactory(
        employee=employee,
        is_primary=False,
        assignment_type=EmployeePositionAssignment.AssignmentType.ACTING,
        end_date=None,
    )
    assert employee.position_assignments.count() == 2


def test_assignment_end_date_before_start_date_rejected():
    assignment = EmployeePositionAssignmentFactory.build(
        start_date=dt.date(2024, 6, 1), end_date=dt.date(2024, 1, 1)
    )
    assignment.employee = EmployeeFactory()
    assignment.position = PositionFactory()
    with pytest.raises(ValidationError):
        assignment.full_clean()


# --- EmployeeManagerAssignment ----------------------------------------------------


def test_only_one_active_primary_manager_per_employee():
    employee = EmployeeFactory()
    EmployeeManagerAssignmentFactory(employee=employee, is_primary=True, end_date=None)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmployeeManagerAssignmentFactory(employee=employee, is_primary=True, end_date=None)


def test_employee_cannot_be_their_own_manager():
    employee = EmployeeFactory()
    assignment = EmployeeManagerAssignment(
        employee=employee, manager=employee, start_date=dt.date(2024, 1, 1)
    )
    with pytest.raises(ValidationError):
        assignment.full_clean()


def test_employee_cannot_be_their_own_manager_database_constraint():
    """Belt-and-suspenders: the CheckConstraint catches it even if `clean()`
    is bypassed (e.g. a bulk `.create()`)."""
    employee = EmployeeFactory()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmployeeManagerAssignment.objects.create(
                employee=employee, manager=employee, start_date=dt.date(2024, 1, 1)
            )


def test_manager_assignment_cycle_rejected():
    """A -> B already reports; attempting B -> A (making A report to B, when
    B already reports to A) must be rejected."""
    employee_a = EmployeeFactory()
    employee_b = EmployeeFactory()
    employee_b.current_manager = employee_a
    employee_b.save()

    reverse_assignment = EmployeeManagerAssignment(
        employee=employee_a, manager=employee_b, start_date=dt.date(2024, 1, 1)
    )
    with pytest.raises(ValidationError):
        reverse_assignment.full_clean()


def test_manager_assignment_end_date_before_start_date_rejected():
    assignment = EmployeeManagerAssignmentFactory.build(
        start_date=dt.date(2024, 6, 1), end_date=dt.date(2024, 1, 1)
    )
    assignment.employee = EmployeeFactory()
    assignment.manager = EmployeeFactory()
    with pytest.raises(ValidationError):
        assignment.full_clean()
