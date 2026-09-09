"""Theme domain models.

See docs/adr/ADR-006-dynamic-theme-architecture.md and
docs/frontend/theme-system.md for the full rationale. Summary:

    Theme (metadata + which Theme is globally active)
      └── ThemeVersion (immutable once published; tokens JSONField)

Only one Theme may have is_active=True at a time — enforced with a
Postgres partial unique constraint, not just application logic, so
concurrent publishes fail safely at the database (Phase 02 plan §3, §8).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import PublicIDModel, TimeStampedModel
from apps.theme.exceptions import ThemeVersionImmutableError


class Theme(TimeStampedModel, PublicIDModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    active_version = models.ForeignKey(
        "theme.ThemeVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=Q(is_active=True), name="theme_single_active"
            ),
        ]
        permissions = [
            ("publish_theme", "Can publish a theme version"),
            ("rollback_theme", "Can roll back a theme"),
            ("activate_theme", "Can activate a theme"),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ThemeVersion(TimeStampedModel, PublicIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    schema_version = models.PositiveIntegerField(default=1)
    tokens = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["theme", "version_number"], name="uniq_theme_version_number"
            ),
        ]
        indexes = [models.Index(fields=["theme", "status"])]
        ordering = ["-version_number"]

    def __str__(self) -> str:
        return f"{self.theme.name} v{self.version_number} ({self.status})"

    def save(self, *args, **kwargs) -> None:
        # Defense-in-depth: services never attempt this, but a published
        # version's tokens must never change even via a direct .save() call
        # (e.g. from Django admin) — see Phase 02 plan §46.
        if self.pk:
            prior = ThemeVersion.objects.filter(pk=self.pk).values("status", "tokens").first()
            if (
                prior
                and prior["status"] == self.Status.PUBLISHED
                and (self.status != self.Status.PUBLISHED or self.tokens != prior["tokens"])
            ):
                raise ThemeVersionImmutableError("Published theme versions cannot be modified.")
        super().save(*args, **kwargs)


class UserThemePreference(TimeStampedModel):
    class Appearance(models.TextChoices):
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"
        SYSTEM = "system", "System"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="theme_preference",
    )
    appearance = models.CharField(
        max_length=8, choices=Appearance.choices, default=Appearance.SYSTEM
    )

    def __str__(self) -> str:
        return f"{self.user_id}: {self.appearance}"
