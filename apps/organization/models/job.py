"""Job master data: JobFamily and JobLevel are real, admin-manageable rows
(genuinely business-configurable, per docs/database/database-conventions.md's
"choices vs. master data" rule) — EmploymentCategory stays a TextChoices
since full-time/part-time/contract are fixed HR categories, not something
McDonald's Pakistan would need to reconfigure without a code change.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel


class JobFamily(TimeStampedModel, PublicIDModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class JobLevel(TimeStampedModel, PublicIDModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    rank = models.PositiveIntegerField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["rank"]

    def __str__(self) -> str:
        return self.name


class Job(TimeStampedModel, PublicIDModel):
    class EmploymentCategory(models.TextChoices):
        FULL_TIME = "full_time", "Full Time"
        PART_TIME = "part_time", "Part Time"
        CONTRACT = "contract", "Contract"
        INTERN = "intern", "Intern"
        TEMPORARY = "temporary", "Temporary"
        OTHER = "other", "Other"

    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    job_family = models.ForeignKey(JobFamily, on_delete=models.PROTECT, related_name="jobs")
    job_level = models.ForeignKey(JobLevel, on_delete=models.PROTECT, related_name="jobs")
    employment_category = models.CharField(max_length=20, choices=EmploymentCategory.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["job_family"]),
            models.Index(fields=["job_level"]),
            models.Index(fields=["code"]),
        ]
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title
