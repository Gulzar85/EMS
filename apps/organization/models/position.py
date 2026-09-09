"""A Position is an organizational seat — independent of both the Job (the
role it performs) and any Employee (who, if anyone, currently occupies it).
See docs/domain/position-management.md.

No `employee` field, no stored `Vacant` status, no PositionHistory table
yet — all deliberate Phase 03 boundaries, see docs/adr/ADR-019-position-
headcount-architecture.md.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel
from apps.organization.validators import assert_no_cycle


class Position(TimeStampedModel, PublicIDModel):
    class PositionType(models.TextChoices):
        INDIVIDUAL_CONTRIBUTOR = "individual_contributor", "Individual Contributor"
        SUPERVISORY = "supervisory", "Supervisory"
        MANAGEMENT = "management", "Management"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        FROZEN = "frozen", "Frozen"
        CLOSED = "closed", "Closed"

    job = models.ForeignKey("organization.Job", on_delete=models.PROTECT, related_name="positions")
    organization_unit = models.ForeignKey(
        "organization.OrganizationUnit",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="positions",
    )
    department = models.ForeignKey(
        "organization.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="positions",
    )
    reports_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="direct_reports"
    )
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=150)
    position_type = models.CharField(
        max_length=30, choices=PositionType.choices, default=PositionType.INDIVIDUAL_CONTRIBUTOR
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    headcount_limit = models.PositiveIntegerField(default=1)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(headcount_limit__gte=1), name="position_headcount_limit_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gte=models.F("effective_from"))
                ),
                name="position_effective_to_after_from",
            ),
        ]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["department"]),
        ]
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"

    def clean(self) -> None:
        super().clean()
        if not self.organization_unit_id and not self.department_id:
            raise ValidationError(
                "A position must be anchored to at least an organization unit or a department."
            )
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError(
                {"effective_to": "Effective-to date cannot be before effective-from."}
            )
        assert_no_cycle(self, self.reports_to, parent_attr="reports_to", field_name="reports_to")

    # --- Headcount calculations -------------------------------------------
    # No EmployeeAssignment model exists yet (Phase 04) — every position
    # reads as fully vacant today. This is the ONE seam Phase 04 changes
    # (occupied_headcount's query), not scattered across call sites. See
    # docs/adr/ADR-019-position-headcount-architecture.md.

    @property
    def occupied_headcount(self) -> int:
        return 0

    @property
    def vacant_headcount(self) -> int:
        return max(self.headcount_limit - self.occupied_headcount, 0)

    @property
    def vacancy_rate(self) -> float:
        if not self.headcount_limit:
            return 0.0
        return round(self.vacant_headcount / self.headcount_limit * 100, 1)

    @property
    def utilization_rate(self) -> float:
        if not self.headcount_limit:
            return 0.0
        return round(self.occupied_headcount / self.headcount_limit * 100, 1)
