"""An employee may list several emergency contacts (Phase 04 brief §13
explicitly rules out OneToOneField) — one may be flagged primary."""

from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel


class EmergencyContact(TimeStampedModel):
    class Relationship(models.TextChoices):
        SPOUSE = "spouse", "Spouse"
        PARENT = "parent", "Parent"
        SIBLING = "sibling", "Sibling"
        CHILD = "child", "Child"
        GUARDIAN = "guardian", "Guardian"
        FRIEND = "friend", "Friend"
        OTHER = "other", "Other"

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="emergency_contacts"
    )
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=20, choices=Relationship.choices)
    mobile_number = models.CharField(max_length=30)
    phone_number = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=models.Q(is_primary=True),
                name="uniq_primary_emergency_contact_per_employee",
            ),
        ]
        indexes = [models.Index(fields=["employee"])]
        ordering = ["-is_primary", "name"]
        verbose_name_plural = "Emergency contacts"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_relationship_display()}) for {self.employee}"
