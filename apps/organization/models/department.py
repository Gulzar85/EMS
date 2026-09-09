"""A department anchors to EITHER an OrganizationUnit (corporate/regional/
area-level, e.g. "Regional Finance") OR a Location (facility-level, e.g.
"Kitchen" at a specific restaurant) — never both, never neither. See
docs/adr/ADR-016-organization-hierarchy.md.

`manager` is deliberately not a field here — it would FK to Employee,
which doesn't exist yet (Phase 04). See docs/adr/ADR-019-position-
headcount-architecture.md for the Employee/EmployeeAssignment seam.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel
from apps.organization.validators import assert_no_cycle


class Department(TimeStampedModel, PublicIDModel):
    organization_unit = models.ForeignKey(
        "organization.OrganizationUnit",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="departments",
    )
    location = models.ForeignKey(
        "organization.Location",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="departments",
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization_unit__isnull=False, location__isnull=True)
                    | models.Q(organization_unit__isnull=True, location__isnull=False)
                ),
                name="department_exactly_one_anchor",
            ),
        ]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["parent"]),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if bool(self.organization_unit_id) == bool(self.location_id):
            raise ValidationError(
                "A department must be anchored to exactly one of organization unit or location."
            )
        assert_no_cycle(self, self.parent, parent_attr="parent", field_name="parent")
