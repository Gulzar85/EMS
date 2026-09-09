"""The source of truth for "who has occupied which Position, and when"
(Phase 04 brief §18-§20). `Employee.current_position` is a denormalized
pointer synchronized from the current primary row here — never the other
way around. See docs/adr/ADR-022.

Deliberately separate from `EmployeeManagerAssignment` (not one bundled
"assignment" table) — see docs/adr/ADR-022 for why: a Position now carries
its own rich identity (Job/Department/OrganizationUnit, per Phase 03),
and an employee can hold a secondary/acting assignment without their
manager changing, so the two facts don't always change together.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


class EmployeePositionAssignment(TimeStampedModel):
    class AssignmentType(models.TextChoices):
        PRIMARY = "primary", "Primary"
        SECONDARY = "secondary", "Secondary"
        ACTING = "acting", "Acting"
        TEMPORARY = "temporary", "Temporary"
        ADDITIONAL_RESPONSIBILITY = "additional_responsibility", "Additional Responsibility"

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="position_assignments"
    )
    position = models.ForeignKey(
        "organization.Position", on_delete=models.PROTECT, related_name="employee_assignments"
    )
    assignment_type = models.CharField(max_length=30, choices=AssignmentType.choices)
    # Which ONE assignment is used for reporting/current_position sync —
    # distinct from `assignment_type`: an "acting" assignment can still be
    # the one that's operationally primary right now (Phase 04 brief §18
    # lists both fields separately for exactly this reason).
    is_primary = models.BooleanField(default=False)

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # NULL = ongoing

    reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=models.Q(is_primary=True, end_date__isnull=True),
                name="uniq_active_primary_position_assignment_per_employee",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(end_date__isnull=True)
                    | models.Q(end_date__gte=models.F("start_date"))
                ),
                name="position_assignment_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["position"]),
            models.Index(fields=["employee", "is_primary", "end_date"]),
        ]
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.employee} → {self.position} ({self.get_assignment_type_display()})"

    @property
    def is_active(self) -> bool:
        return self.end_date is None

    def clean(self) -> None:
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})
