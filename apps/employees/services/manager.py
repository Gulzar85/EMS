"""Manager-assignment write operations — the only place
`Employee.current_manager` is ever set (Phase 04 brief §25-§26).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import record as record_audit
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.models import Employee, EmployeeManagerAssignment


class EmployeeManagerService:
    @staticmethod
    @transaction.atomic
    def assign_manager(
        *,
        employee: Employee,
        manager: Employee,
        relationship_type: str = EmployeeManagerAssignment.RelationshipType.DIRECT,
        is_primary: bool = True,
        start_date=None,
        actor: User | None,
    ) -> EmployeeManagerAssignment:
        if employee.pk == manager.pk:
            raise EmployeeValidationError("An employee cannot be their own manager.")

        start_date = start_date or timezone.localdate()
        before_manager = employee.current_manager if is_primary else None

        if is_primary:
            previous_primary = (
                employee.manager_assignments.select_for_update()
                .filter(is_primary=True, end_date__isnull=True)
                .first()
            )
            if previous_primary:
                if previous_primary.manager_id == manager.id:
                    raise EmployeeValidationError("This is already the employee's manager.")
                previous_primary.end_date = start_date
                previous_primary.full_clean()
                previous_primary.save(update_fields=["end_date", "updated_at"])

        assignment = EmployeeManagerAssignment(
            employee=employee,
            manager=manager,
            relationship_type=relationship_type,
            is_primary=is_primary,
            start_date=start_date,
        )
        assignment.full_clean()  # raises on cycles — see EmployeeManagerAssignment.clean()
        assignment.save()

        if is_primary:
            employee.current_manager = manager
            employee.save(update_fields=["current_manager", "updated_at"])

        record_audit(
            actor=actor,
            action="employee.manager_changed",
            entity=employee,
            before={"manager": str(before_manager) if before_manager else None},
            after={"manager": str(manager)},
        )
        return assignment

    @staticmethod
    @transaction.atomic
    def end_manager_assignment(
        *, assignment: EmployeeManagerAssignment, end_date=None, actor: User | None
    ) -> EmployeeManagerAssignment:
        if assignment.end_date is not None:
            raise EmployeeValidationError("This manager assignment has already ended.")

        end_date = end_date or timezone.localdate()
        assignment.end_date = end_date
        assignment.full_clean()
        assignment.save()

        employee = assignment.employee
        if assignment.is_primary and employee.current_manager_id == assignment.manager_id:
            employee.current_manager = None
            employee.save(update_fields=["current_manager", "updated_at"])

        record_audit(
            actor=actor,
            action="employee.manager_assignment_ended",
            entity=employee,
            after={"manager": str(assignment.manager), "end_date": str(end_date)},
        )
        return assignment
