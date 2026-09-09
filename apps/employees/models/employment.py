"""Employment lifecycle facts — split from `Employee` per Phase 04 brief
§14/§17: this is what changes as the employment relationship itself
progresses (probation, confirmation, termination), never edited via a
generic form — only through `apps.employees.services.EmployeeLifecycleService`
transitions, each of which is audited (see docs/adr/ADR-024).

`employment_type` reuses `organization.Job.EmploymentCategory` rather than
defining a second, parallel set of choices (Phase 04 brief §16) — a
specific employee's actual contract type and their job's *typical*
category are related but distinct facts (a normally full-time "Cashier"
job can still have a part-time incumbent), so the field lives here, not
derived from Job, but the vocabulary is shared.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel
from apps.organization.models import Job


class EmployeeEmployment(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PROBATION = "probation", "Probation"
        ACTIVE = "active", "Active"
        ON_LEAVE = "on_leave", "On Leave"
        SUSPENDED = "suspended", "Suspended"
        RESIGNED = "resigned", "Resigned"
        TERMINATED = "terminated", "Terminated"
        RETIRED = "retired", "Retired"

    employee = models.OneToOneField(
        "employees.Employee", on_delete=models.CASCADE, related_name="employment"
    )

    joining_date = models.DateField()
    service_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Defaults to the joining date; differs only when past service counts "
        "toward seniority (e.g. a documented rehire adjustment).",
    )
    employment_type = models.CharField(max_length=20, choices=Job.EmploymentCategory.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    probation_end_date = models.DateField(null=True, blank=True)
    confirmation_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)
    termination_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(termination_date__isnull=True)
                    | models.Q(termination_date__gte=models.F("joining_date"))
                ),
                name="employment_termination_after_joining",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(probation_end_date__isnull=True)
                    | models.Q(probation_end_date__gte=models.F("joining_date"))
                ),
                name="employment_probation_end_after_joining",
            ),
        ]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"Employment for {self.employee} ({self.get_status_display()})"

    def clean(self) -> None:
        super().clean()
        if self.termination_date and self.termination_date < self.joining_date:
            raise ValidationError(
                {"termination_date": "Termination date cannot be before the joining date."}
            )
        if self.probation_end_date and self.probation_end_date < self.joining_date:
            raise ValidationError(
                {"probation_end_date": "Probation end date cannot be before the joining date."}
            )
