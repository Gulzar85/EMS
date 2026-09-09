"""Contact details, split from `Employee` so the identity record stays
lean and the "Contact Information" profile section (Phase 04 brief §11,
§31) maps to one model. A single embedded address (not a separate
multi-type `EmployeeAddress` table) — the same deliberate simplification
Phase 03 made for `Location.address` — see docs/adr/ADR-020.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class EmployeeContact(TimeStampedModel):
    employee = models.OneToOneField(
        "employees.Employee", on_delete=models.CASCADE, related_name="contact"
    )

    # Personal email is deliberately NOT unique — people share family email
    # addresses and reuse old ones across employers (Phase 04 brief §58).
    personal_email = models.EmailField(blank=True)
    # Work email is the identifier colleagues actually use to reach this
    # person day to day, so it's unique whenever it's set.
    work_email = models.EmailField(blank=True)

    mobile_number = models.CharField(max_length=30, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)

    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default="Pakistan")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["work_email"],
                condition=~Q(work_email=""),
                name="uniq_employee_contact_work_email",
            ),
        ]

    def __str__(self) -> str:
        return f"Contact for {self.employee}"
