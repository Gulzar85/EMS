"""Employee identity + contact write operations. Employment-lifecycle
fields (status, probation, termination) are deliberately NOT editable
through this service — only through `EmployeeLifecycleService`, so every
status change is an audited, validated transition rather than a free-form
field edit (Phase 04 brief §27, §91).
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.audit.services import record as record_audit
from apps.employees.models import Employee, EmployeeContact, EmployeeEmployment
from apps.employees.services.number import EmployeeNumberService

_EMPLOYEE_FIELDS = {
    "first_name",
    "middle_name",
    "last_name",
    "preferred_name",
    "date_of_birth",
    "gender",
    "nationality",
    "marital_status",
    "profile_photo",
}
_CONTACT_FIELDS = {
    "personal_email",
    "work_email",
    "mobile_number",
    "phone_number",
    "address_line_1",
    "address_line_2",
    "city",
    "district",
    "province",
    "postal_code",
    "country",
}


class EmployeeService:
    @staticmethod
    @transaction.atomic
    def create_employee(
        *,
        joining_date,
        employment_type: str,
        probation_end_date=None,
        actor: User | None,
        **fields,
    ) -> Employee:
        employee_fields = {k: v for k, v in fields.items() if k in _EMPLOYEE_FIELDS}
        contact_fields = {k: v for k, v in fields.items() if k in _CONTACT_FIELDS}

        employee = Employee(employee_number=EmployeeNumberService.generate(), **employee_fields)
        employee.full_clean()
        employee.save()

        contact = EmployeeContact(employee=employee, **contact_fields)
        contact.full_clean()
        contact.save()

        employment = EmployeeEmployment(
            employee=employee,
            joining_date=joining_date,
            employment_type=employment_type,
            probation_end_date=probation_end_date,
        )
        employment.full_clean()
        employment.save()

        record_audit(
            actor=actor,
            action="employee.created",
            entity=employee,
            after={"employee_number": employee.employee_number, "name": employee.display_name},
        )
        return employee

    @staticmethod
    @transaction.atomic
    def update_employee(*, employee: Employee, actor: User | None, **fields) -> Employee:
        before = {"display_name": employee.display_name}
        contact = employee.contact
        contact_changed = False

        for field, value in fields.items():
            if field in _EMPLOYEE_FIELDS:
                setattr(employee, field, value)
            elif field in _CONTACT_FIELDS:
                setattr(contact, field, value)
                contact_changed = True

        employee.full_clean()
        employee.save()
        if contact_changed:
            contact.full_clean()
            contact.save()

        record_audit(
            actor=actor,
            action="employee.updated",
            entity=employee,
            before=before,
            after={"display_name": employee.display_name},
        )
        return employee
