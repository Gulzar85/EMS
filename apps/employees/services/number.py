"""Employee number generation — see docs/adr/ADR-021.

Never derives a business identifier from the database primary key (Phase
04 brief §9): a `select_for_update()`-locked singleton counter row is the
one source of the next value, making generation safe under concurrent
requests without relying on Python-level checks (brief §56).
"""

from __future__ import annotations

from django.conf import settings
from django.db import transaction

from apps.employees.models import EmployeeNumberSequence


class EmployeeNumberService:
    @staticmethod
    @transaction.atomic
    def generate() -> str:
        sequence, _ = EmployeeNumberSequence.objects.select_for_update().get_or_create(pk=1)
        sequence.last_value += 1
        sequence.save(update_fields=["last_value"])
        padding = settings.EMPLOYEE_NUMBER_PADDING
        return f"{settings.EMPLOYEE_NUMBER_PREFIX}{sequence.last_value:0{padding}d}"
