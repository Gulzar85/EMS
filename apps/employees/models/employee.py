"""The employee identity record. Deliberately does NOT hold a separate
`Person` layer (see docs/adr/ADR-020-employee-identity-model.md for why
that Phase 00 sketch is deferred, not abandoned) and does NOT carry its
own `is_active` boolean (see docs/adr/ADR-024) — active/inactive is always
read from `EmployeeEmployment.status`.

`current_position` / `current_manager` are deliberately denormalized
pointers, not the source of truth — see docs/adr/ADR-022. The source of
truth for "who has held which position/reported to whom, and when" is
`EmployeePositionAssignment` / `EmployeeManagerAssignment`.
"""

from __future__ import annotations

import uuid

from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel
from apps.employees.constants import CURRENTLY_EMPLOYED_STATUSES
from apps.employees.validators import validate_profile_photo


def _profile_photo_upload_path(instance: Employee, filename: str) -> str:
    # Never trust the client-supplied filename in a storage path — an
    # attacker-controlled name could otherwise be used for path traversal
    # or to overwrite another employee's file. Only the extension survives.
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"employees/profile-photos/{instance.public_id}/{uuid.uuid4()}.{extension}"


class Employee(TimeStampedModel, PublicIDModel):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        UNDISCLOSED = "undisclosed", "Prefer not to say"

    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "Single"
        MARRIED = "married", "Married"
        DIVORCED = "divorced", "Divorced"
        WIDOWED = "widowed", "Widowed"
        OTHER = "other", "Other"

    employee_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.OneToOneField(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee",
    )

    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    preferred_name = models.CharField(max_length=100, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default="Pakistani")
    marital_status = models.CharField(max_length=20, choices=MaritalStatus.choices, blank=True)

    profile_photo = models.ImageField(
        upload_to=_profile_photo_upload_path,
        null=True,
        blank=True,
        validators=[validate_profile_photo],
    )

    # --- Denormalized "current state" pointers ------------------------
    # Synchronized ONLY by apps.employees.services (EmployeeAssignmentService
    # / EmployeeManagerService) inside the same transaction as the
    # EmployeePositionAssignment / EmployeeManagerAssignment row that backs
    # them. Never set directly from a view or form. See ADR-022.
    current_position = models.ForeignKey(
        "organization.Position",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_employees",
    )
    current_manager = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="direct_reports",
    )

    class Meta:
        indexes = [
            models.Index(fields=["employee_number"]),
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["current_position"]),
            models.Index(fields=["current_manager"]),
        ]
        ordering = ["employee_number"]

    def __str__(self) -> str:
        return f"{self.employee_number} — {self.display_name}"

    # --- Derived, never-stored data -------------------------------------

    @property
    def display_name(self) -> str:
        return self.preferred_name or f"{self.first_name} {self.last_name}".strip()

    @property
    def full_legal_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(part for part in parts if part)

    @property
    def is_active(self) -> bool:
        """Whether this employee currently has a live employment
        relationship. Deliberately NOT a stored field — see ADR-024:
        `Employee.is_active` and `EmployeeEmployment.status` would
        otherwise be two independently-editable facts that can contradict
        each other.
        """
        employment = getattr(self, "employment", None)
        return bool(employment) and employment.status in CURRENTLY_EMPLOYED_STATUSES
