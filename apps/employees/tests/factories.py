from __future__ import annotations

import datetime as dt

import factory
from factory.django import DjangoModelFactory

from apps.employees.models import (
    EmergencyContact,
    Employee,
    EmployeeContact,
    EmployeeEmployment,
    EmployeeManagerAssignment,
    EmployeePositionAssignment,
)
from apps.organization.models import Job
from apps.organization.tests.factories import PositionFactory


class EmployeeFactory(DjangoModelFactory):
    class Meta:
        model = Employee

    employee_number = factory.Sequence(lambda n: f"EMP-{n:06d}")
    first_name = factory.Sequence(lambda n: f"First{n}")
    last_name = factory.Sequence(lambda n: f"Last{n}")


class EmployeeContactFactory(DjangoModelFactory):
    class Meta:
        model = EmployeeContact

    employee = factory.SubFactory(EmployeeFactory)
    work_email = factory.Sequence(lambda n: f"employee{n}@mcdonalds.com.pk")


class EmployeeEmploymentFactory(DjangoModelFactory):
    class Meta:
        model = EmployeeEmployment

    employee = factory.SubFactory(EmployeeFactory)
    joining_date = dt.date(2024, 1, 1)
    employment_type = Job.EmploymentCategory.FULL_TIME
    status = EmployeeEmployment.Status.ACTIVE


def make_employee(**kwargs) -> Employee:
    """A fully-formed Employee — identity + contact + employment rows,
    matching what `EmployeeService.create_employee` actually produces.
    Most tests want this, not a bare `Employee` row missing its required
    OneToOne siblings."""
    employment_kwargs = {}
    for key in ("status", "joining_date", "employment_type", "probation_end_date"):
        if key in kwargs:
            employment_kwargs[key] = kwargs.pop(key)
    employee = EmployeeFactory(**kwargs)
    EmployeeContactFactory(employee=employee)
    EmployeeEmploymentFactory(employee=employee, **employment_kwargs)
    return employee


class EmergencyContactFactory(DjangoModelFactory):
    class Meta:
        model = EmergencyContact

    employee = factory.SubFactory(EmployeeFactory)
    name = factory.Sequence(lambda n: f"Emergency Contact {n}")
    relationship = EmergencyContact.Relationship.PARENT
    mobile_number = "03001234567"


class EmployeePositionAssignmentFactory(DjangoModelFactory):
    class Meta:
        model = EmployeePositionAssignment

    employee = factory.SubFactory(EmployeeFactory)
    position = factory.SubFactory(PositionFactory)
    assignment_type = EmployeePositionAssignment.AssignmentType.PRIMARY
    is_primary = True
    start_date = dt.date(2024, 1, 1)


class EmployeeManagerAssignmentFactory(DjangoModelFactory):
    class Meta:
        model = EmployeeManagerAssignment

    employee = factory.SubFactory(EmployeeFactory)
    manager = factory.SubFactory(EmployeeFactory)
    is_primary = True
    start_date = dt.date(2024, 1, 1)
