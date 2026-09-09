"""Operational profile for a Location whose location_type is RESTAURANT.

A supertype/subtype split (OneToOne to Location), not a merged table —
future facility profiles (e.g. a TrainingCenter with its own fields) can
be added the same way without touching Location. name/code are NOT
duplicated here; read through location.name / location.code (Phase 03
plan judgment call #2).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel


class Restaurant(TimeStampedModel, PublicIDModel):
    class RestaurantType(models.TextChoices):
        STANDALONE = "standalone", "Standalone"
        DRIVE_THRU = "drive_thru", "Drive-Thru"
        MALL_KIOSK = "mall_kiosk", "Mall/Kiosk"
        OTHER = "other", "Other"

    class OperationalStatus(models.TextChoices):
        OPERATING = "operating", "Operating"
        TEMPORARILY_CLOSED = "temporarily_closed", "Temporarily Closed"
        UNDER_RENOVATION = "under_renovation", "Under Renovation"
        CLOSED = "closed", "Closed"
        PLANNED = "planned", "Planned"

    location = models.OneToOneField(
        "organization.Location", on_delete=models.PROTECT, related_name="restaurant"
    )
    restaurant_number = models.CharField(max_length=20, unique=True)
    restaurant_type = models.CharField(
        max_length=20, choices=RestaurantType.choices, default=RestaurantType.STANDALONE
    )
    operational_status = models.CharField(
        max_length=20, choices=OperationalStatus.choices, default=OperationalStatus.PLANNED
    )
    opening_date = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(closing_date__isnull=True)
                | models.Q(closing_date__gte=models.F("opening_date")),
                name="restaurant_closing_date_after_opening_date",
            ),
        ]
        indexes = [
            models.Index(fields=["restaurant_number"]),
            models.Index(fields=["operational_status"]),
        ]
        ordering = ["restaurant_number"]

    def __str__(self) -> str:
        return f"{self.restaurant_number} — {self.location.name}"

    def clean(self) -> None:
        super().clean()
        if self.closing_date and self.opening_date and self.closing_date < self.opening_date:
            raise ValidationError(
                {"closing_date": "Closing date cannot be before the opening date."}
            )
