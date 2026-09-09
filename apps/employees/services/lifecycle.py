"""Employee lifecycle transitions — a clean state model, not a workflow
engine (Phase 04 brief §27): each transition validates the current status,
writes to `EmployeeEmployment`, and audits the change, mirroring exactly
the pattern `apps.organization.services._transition_position` established
in Phase 03.

    DRAFT -> PROBATION (or ACTIVE, if no probation_end_date) -> ACTIVE
    ACTIVE <-> ON_LEAVE
    ACTIVE <-> SUSPENDED
    {PROBATION, ACTIVE, ON_LEAVE, SUSPENDED} -> {RESIGNED, TERMINATED, RETIRED}  (terminal)
"""

from __future__ import annotations

import datetime as dt

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import record as record_audit
from apps.employees.constants import TERMINAL_EMPLOYMENT_STATUSES
from apps.employees.exceptions import EmployeeValidationError
from apps.employees.models import Employee, EmployeeEmployment

Status = EmployeeEmployment.Status


def _transition(
    employment: EmployeeEmployment,
    *,
    new_status: str,
    action: str,
    actor: User | None,
    reason: str = "",
    extra_fields: tuple[str, ...] = (),
) -> EmployeeEmployment:
    before_status = employment.status
    employment.status = new_status
    employment.full_clean()
    employment.save(update_fields=["status", "updated_at", *extra_fields])
    record_audit(
        actor=actor,
        action=action,
        entity=employment.employee,
        before={"status": before_status},
        after={"status": new_status},
        reason=reason,
    )
    return employment


class EmployeeLifecycleService:
    @staticmethod
    @transaction.atomic
    def activate(*, employee: Employee, actor: User | None, reason: str = "") -> EmployeeEmployment:
        employment = employee.employment
        if employment.status != Status.DRAFT:
            raise EmployeeValidationError("Only a draft employee can be activated.")
        target = Status.PROBATION if employment.probation_end_date else Status.ACTIVE
        return _transition(employment, new_status=target, action="employee.activated", actor=actor, reason=reason)

    @staticmethod
    @transaction.atomic
    def confirm(*, employee: Employee, actor: User | None, reason: str = "") -> EmployeeEmployment:
        employment = employee.employment
        if employment.status != Status.PROBATION:
            raise EmployeeValidationError("Only an employee on probation can be confirmed.")
        employment.confirmation_date = timezone.localdate()
        return _transition(
            employment,
            new_status=Status.ACTIVE,
            action="employee.confirmed",
            actor=actor,
            reason=reason,
            extra_fields=("confirmation_date",),
        )

    @staticmethod
    @transaction.atomic
    def place_on_leave(*, employee: Employee, actor: User | None, reason: str = "") -> EmployeeEmployment:
        employment = employee.employment
        if employment.status != Status.ACTIVE:
            raise EmployeeValidationError("Only an active employee can be placed on leave.")
        return _transition(employment, new_status=Status.ON_LEAVE, action="employee.placed_on_leave", actor=actor, reason=reason)

    @staticmethod
    @transaction.atomic
    def return_from_leave(*, employee: Employee, actor: User | None, reason: str = "") -> EmployeeEmployment:
        employment = employee.employment
        if employment.status != Status.ON_LEAVE:
            raise EmployeeValidationError("Only an employee on leave can return from leave.")
        return _transition(employment, new_status=Status.ACTIVE, action="employee.returned_from_leave", actor=actor, reason=reason)

    @staticmethod
    @transaction.atomic
    def suspend(*, employee: Employee, actor: User | None, reason: str = "") -> EmployeeEmployment:
        employment = employee.employment
        if employment.status != Status.ACTIVE:
            raise EmployeeValidationError("Only an active employee can be suspended.")
        return _transition(employment, new_status=Status.SUSPENDED, action="employee.suspended", actor=actor, reason=reason)

    @staticmethod
    @transaction.atomic
    def reinstate(*, employee: Employee, actor: User | None, reason: str = "") -> EmployeeEmployment:
        employment = employee.employment
        if employment.status != Status.SUSPENDED:
            raise EmployeeValidationError("Only a suspended employee can be reinstated.")
        return _transition(employment, new_status=Status.ACTIVE, action="employee.reinstated", actor=actor, reason=reason)

    @staticmethod
    @transaction.atomic
    def deactivate(
        *,
        employee: Employee,
        status: str,
        reason: str,
        effective_date: dt.date | None = None,
        actor: User | None,
    ) -> EmployeeEmployment:
        if status not in TERMINAL_EMPLOYMENT_STATUSES:
            raise EmployeeValidationError(
                "Deactivation must target resigned, terminated, or retired."
            )
        employment = employee.employment
        if employment.status in TERMINAL_EMPLOYMENT_STATUSES:
            raise EmployeeValidationError("This employee's employment has already ended.")

        employment.termination_date = effective_date or timezone.localdate()
        employment.termination_reason = reason
        return _transition(
            employment,
            new_status=status,
            action="employee.deactivated",
            actor=actor,
            reason=reason,
            extra_fields=("termination_date", "termination_reason"),
        )
