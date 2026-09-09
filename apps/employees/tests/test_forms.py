import datetime as dt

import pytest

from apps.employees.forms import (
    EmployeeCreateForm,
    EmployeeProfileForm,
    ManagerAssignmentForm,
    PositionAssignmentEndForm,
)
from apps.employees.tests.factories import (
    EmployeeFactory,
    EmployeePositionAssignmentFactory,
    make_employee,
)
from apps.organization.models import Job

pytestmark = pytest.mark.django_db


# --- EmployeeCreateForm --------------------------------------------------------


def test_employee_create_form_valid_data():
    data = {
        "first_name": "Ali",
        "last_name": "Raza",
        "joining_date": "2024-01-01",
        "employment_type": Job.EmploymentCategory.FULL_TIME,
    }
    form = EmployeeCreateForm(data)
    assert form.is_valid(), form.errors


def test_employee_create_form_requires_joining_date():
    data = {"first_name": "Ali", "last_name": "Raza", "employment_type": Job.EmploymentCategory.FULL_TIME}
    form = EmployeeCreateForm(data)
    assert not form.is_valid()
    assert "joining_date" in form.errors


# --- EmployeeProfileForm --------------------------------------------------------


def test_profile_form_from_employee_populates_initial():
    employee = make_employee(first_name="Existing", last_name="Person")
    employee.contact.work_email = "existing@mcdonalds.com.pk"
    employee.contact.save()

    form = EmployeeProfileForm.from_employee(employee)

    assert form.initial["first_name"] == "Existing"
    assert form.initial["work_email"] == "existing@mcdonalds.com.pk"


def test_profile_form_does_not_expose_employment_fields():
    """Employment status/joining date must never be editable through the
    generic profile form (Phase 04 brief §27, §91)."""
    assert "joining_date" not in EmployeeProfileForm.base_fields
    assert "employment_type" not in EmployeeProfileForm.base_fields


# --- PositionAssignmentEndForm --------------------------------------------------


def test_end_form_rejects_end_date_before_assignment_start():
    assignment = EmployeePositionAssignmentFactory(start_date=dt.date(2024, 6, 1))
    form = PositionAssignmentEndForm({"end_date": "2024-01-01", "reason": ""}, assignment=assignment)
    assert not form.is_valid()
    assert "end_date" in form.errors


def test_end_form_accepts_end_date_after_assignment_start():
    assignment = EmployeePositionAssignmentFactory(start_date=dt.date(2024, 1, 1))
    form = PositionAssignmentEndForm({"end_date": "2024-06-01", "reason": ""}, assignment=assignment)
    assert form.is_valid(), form.errors


# --- ManagerAssignmentForm --------------------------------------------------------


def test_manager_form_excludes_the_employee_themselves():
    employee = EmployeeFactory()
    EmployeeFactory()  # another employee who SHOULD appear
    form = ManagerAssignmentForm(employee=employee)
    assert employee not in form.fields["manager"].queryset


def test_manager_form_includes_other_employees():
    employee = EmployeeFactory()
    other = EmployeeFactory()
    form = ManagerAssignmentForm(employee=employee)
    assert other in form.fields["manager"].queryset
