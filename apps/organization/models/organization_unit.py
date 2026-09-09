"""The administrative/geographic hierarchy: Company -> Corporate -> Region ->
Area (-> BusinessUnit at any level for corporate support functions).

Deliberately does NOT include Restaurant or Department as unit types —
see docs/adr/ADR-016-organization-hierarchy.md for the full reasoning.
Restaurant/Department need real fields a generic tree node shouldn't
carry, and giving every restaurant a redundant "thin" OrganizationUnit
row plus a "rich" profile row is bookkeeping with no benefit.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel
from apps.organization.validators import assert_no_cycle


class OrganizationUnit(TimeStampedModel, PublicIDModel):
    class UnitType(models.TextChoices):
        CORPORATE = "corporate", "Corporate"
        REGION = "region", "Region"
        AREA = "area", "Area"
        BUSINESS_UNIT = "business_unit", "Business Unit"
        OTHER = "other", "Other"

    # Which parent unit_types are allowed for a given child unit_type. An
    # empty set means "must be a root node" (only CORPORATE qualifies).
    ALLOWED_PARENT_TYPES: dict[str, set[str]] = {
        UnitType.CORPORATE: set(),
        UnitType.REGION: {UnitType.CORPORATE},
        UnitType.AREA: {UnitType.REGION},
        UnitType.BUSINESS_UNIT: {UnitType.CORPORATE, UnitType.REGION, UnitType.AREA},
        UnitType.OTHER: {
            UnitType.CORPORATE,
            UnitType.REGION,
            UnitType.AREA,
            UnitType.BUSINESS_UNIT,
            UnitType.OTHER,
        },
    }

    company = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="organization_units"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    unit_type = models.CharField(max_length=20, choices=UnitType.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_org_unit_company_code"),
        ]
        indexes = [
            models.Index(fields=["parent"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["company", "unit_type"]),
        ]
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()

        if self.unit_type == self.UnitType.CORPORATE:
            if self.parent is not None:
                raise ValidationError(
                    {"parent": "A Corporate unit must be a root node (no parent)."}
                )
            return

        if self.parent is None:
            raise ValidationError({"parent": "This unit type requires a parent unit."})

        allowed = self.ALLOWED_PARENT_TYPES.get(self.unit_type, set())
        if self.parent.unit_type not in allowed:
            raise ValidationError(
                {
                    "parent": (
                        f"A {self.get_unit_type_display()} cannot have a parent of type "
                        f"{self.parent.get_unit_type_display()}."
                    )
                }
            )

        assert_no_cycle(self, self.parent, parent_attr="parent", field_name="parent")
