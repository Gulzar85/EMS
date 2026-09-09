"""A single-row counter backing `EmployeeNumberService` — see
docs/adr/ADR-021-employee-number-generation.md. Deliberately a plain table
+ `select_for_update()` rather than a raw Postgres `SEQUENCE`: it stays
Django-native, portable, and trivially testable, and McDonald's Pakistan's
actual hiring throughput never approaches a rate where row-level locking
here would be a bottleneck.
"""

from __future__ import annotations

from django.db import models


class EmployeeNumberSequence(models.Model):
    """Singleton row (always pk=1). `last_value` is the last employee
    number issued; the next one is `last_value + 1`."""

    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Employee number sequence"
        verbose_name_plural = "Employee number sequence"

    def __str__(self) -> str:
        return f"Employee number sequence (last: {self.last_value})"
