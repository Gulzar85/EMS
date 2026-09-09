"""The source of truth for "who reported to whom, and when" (Phase 04
brief §25-§26). `Employee.current_manager` is a denormalized pointer
synchronized from the current primary row here. See docs/adr/ADR-022.

Cycle prevention is service/validator-level (`apps.employees.validators.
assert_no_manager_cycle`), not a DB constraint — a reporting cycle spans
multiple rows across multiple employees, which CheckConstraint cannot
express.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel
from apps.employees.validators import assert_no_manager_cycle


class EmployeeManagerAssignment(TimeStampedModel):
    class RelationshipType(models.TextChoices):
        DIRECT = "direct", "Direct"
        DOTTED_LINE = "dotted_line", "Dotted Line"

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="manager_assignments"
    )
    manager = models.ForeignKey(
        "employees.Employee", on_delete=models.PROTECT, related_name="direct_report_assignments"
    )
    relationship_type = models.CharField(
        max_length=20, choices=RelationshipType.choices, default=RelationshipType.DIRECT
    )
    is_primary = models.BooleanField(default=True)

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # NULL = ongoing

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=models.Q(is_primary=True, end_date__isnull=True),
                name="uniq_active_primary_manager_assignment_per_employee",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(end_date__isnull=True)
                    | models.Q(end_date__gte=models.F("start_date"))
                ),
                name="manager_assignment_end_after_start",
            ),
            models.CheckConstraint(
                condition=~models.Q(employee=models.F("manager")),
                name="manager_assignment_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["manager"]),
            models.Index(fields=["employee", "is_primary", "end_date"]),
        ]
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.employee} reports to {self.manager}"

    @property
    def is_active(self) -> bool:
        return self.end_date is None

    def clean(self) -> None:
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})
        if self.employee_id and self.manager_id and self.employee_id == self.manager_id:
            raise ValidationError({"manager": "An employee cannot be their own manager."})
        if self.employee_id and self.manager_id:
            assert_no_manager_cycle(self.employee, self.manager)
