"""Reusable abstract base models — genuinely cross-cutting only.

Per docs/database/database-conventions.md: BigAutoField is the real primary
key everywhere (DEFAULT_AUTO_FIELD, see config/settings/base.py); a separate
`public_id` is added only on models addressed by URL or a future API.

No business-domain models belong in this app — see docs/architecture/
django-app-map.md for what `core` is (and isn't) responsible for.
"""

from __future__ import annotations

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """created_at / updated_at, present on nearly every model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicIDModel(models.Model):
    """Adds a non-enumerable `public_id` for models referenced by URL or API.

    See docs/adr/ADR-003-uuid-strategy.md — the integer PK stays the real,
    fast, internally-used primary key; `public_id` is what appears in URLs.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    class Meta:
        abstract = True
