"""Linking/unlinking an Employee to a login User — deliberately a distinct,
explicit action, never automatic (Phase 04 brief §49-§51): most employees
(restaurant crew) never get a login account, and creating one for every
Employee row would be unrequested scope.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.audit.services import record as record_audit
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.models import Employee


class EmployeeUserLinkService:
    @staticmethod
    @transaction.atomic
    def link_user(*, employee: Employee, user: User, actor: User | None) -> Employee:
        if employee.user_id is not None:
            raise EmployeeValidationError("This employee is already linked to a user account.")
        if Employee.objects.filter(user=user).exclude(pk=employee.pk).exists():
            raise EmployeeValidationError("This user account is already linked to another employee.")

        employee.user = user
        employee.full_clean()
        employee.save(update_fields=["user", "updated_at"])
        record_audit(
            actor=actor, action="employee.user_linked", entity=employee, after={"user": user.email}
        )
        return employee

    @staticmethod
    @transaction.atomic
    def unlink_user(*, employee: Employee, actor: User | None) -> Employee:
        if employee.user_id is None:
            raise EmployeeValidationError("This employee has no linked user account.")

        before_email = employee.user.email
        employee.user = None
        employee.full_clean()
        employee.save(update_fields=["user", "updated_at"])
        record_audit(
            actor=actor,
            action="employee.user_unlinked",
            entity=employee,
            before={"user": before_email},
        )
        return employee
