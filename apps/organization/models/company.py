"""The configurable organization root — never hardcode "McDonald's Pakistan"
into application logic; it's seeded data (see management/commands/
seed_organization.py), not a constant.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import PublicIDModel, TimeStampedModel


class Company(TimeStampedModel, PublicIDModel):
    name = models.CharField(max_length=150, unique=True)
    legal_name = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=20, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "companies"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
