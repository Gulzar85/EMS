"""Position-assignment write operations — the only place
`Employee.current_position` is ever set (Phase 04 brief §18-§20, §24).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import record as record_audit
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.models import Employee, EmployeePositionAssignment
from apps.organization.models import Position


class EmployeeAssignmentService:
    @staticmethod
    @transaction.atomic
    def assign_position(
        *,
        employee: Employee,
        position: Position,
        assignment_type: str,
        is_primary: bool = False,
        start_date=None,
        reason: str = "",
        notes: str = "",
        actor: User | None,
    ) -> EmployeePositionAssignment:
        start_date = start_date or timezone.localdate()

        if is_primary:
            previous_primary = (
                employee.position_assignments.select_for_update()
                .filter(is_primary=True, end_date__isnull=True)
                .first()
            )
            if previous_primary:
                if previous_primary.position_id == position.id:
                    raise EmployeeValidationError(
                        "This is already the employee's primary position."
                    )
                previous_primary.end_date = start_date
                previous_primary.full_clean()
                previous_primary.save(update_fields=["end_date", "updated_at"])

        assignment = EmployeePositionAssignment(
            employee=employee,
            position=position,
            assignment_type=assignment_type,
            is_primary=is_primary,
            start_date=start_date,
            reason=reason,
            notes=notes,
        )
        assignment.full_clean()
        assignment.save()

        if is_primary:
            employee.current_position = position
            employee.save(update_fields=["current_position", "updated_at"])

        record_audit(
            actor=actor,
            action="employee.position_assigned",
            entity=employee,
            after={
                "position": position.code,
                "assignment_type": assignment_type,
                "is_primary": is_primary,
            },
            reason=reason,
        )
        return assignment

    @staticmethod
    @transaction.atomic
    def end_assignment(
        *, assignment: EmployeePositionAssignment, end_date=None, reason: str = "", actor: User | None
    ) -> EmployeePositionAssignment:
        if assignment.end_date is not None:
            raise EmployeeValidationError("This assignment has already ended.")

        end_date = end_date or timezone.localdate()
        assignment.end_date = end_date
        assignment.full_clean()
        assignment.save()

        employee = assignment.employee
        if assignment.is_primary and employee.current_position_id == assignment.position_id:
            employee.current_position = None
            employee.save(update_fields=["current_position", "updated_at"])

        record_audit(
            actor=actor,
            action="employee.position_assignment_ended",
            entity=employee,
            after={"position": assignment.position.code, "end_date": str(end_date)},
            reason=reason,
        )
        return assignment
