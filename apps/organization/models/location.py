"""Any physical facility — restaurant, office, warehouse, training center.
See docs/adr/ADR-016-organization-hierarchy.md for why this is a separate
model from OrganizationUnit (rich physical/contact fields that don't
belong on a generic tree node) and from Restaurant (a Location profile,
not every Location is a restaurant).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel


class Location(TimeStampedModel, PublicIDModel):
    class LocationType(models.TextChoices):
        RESTAURANT = "restaurant", "Restaurant"
        OFFICE = "office", "Office"
        WAREHOUSE = "warehouse", "Warehouse"
        TRAINING_CENTER = "training_center", "Training Center"
        OTHER = "other", "Other"

    organization_unit = models.ForeignKey(
        "organization.OrganizationUnit", on_delete=models.PROTECT, related_name="locations"
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    location_type = models.CharField(max_length=20, choices=LocationType.choices)

    # Kept as plain indexed CharFields rather than normalized Province/
    # District/City reference tables — a deliberate Phase 03 simplification
    # (see docs/domain/organization.md), not an oversight. Adding those
    # tables later is additive, not a restructure of this model.
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    is_active = models.BooleanField(default=True)
    opened_on = models.DateField(null=True, blank=True)
    closed_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(closed_on__isnull=True)
                | models.Q(closed_on__gte=models.F("opened_on")),
                name="location_closed_on_after_opened_on",
            ),
        ]
        indexes = [
            models.Index(fields=["location_type"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["organization_unit"]),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def clean(self) -> None:
        super().clean()
        if self.closed_on and self.opened_on and self.closed_on < self.opened_on:
            raise ValidationError({"closed_on": "Closed date cannot be before the opened date."})
