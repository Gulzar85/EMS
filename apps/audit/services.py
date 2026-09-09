"""The audit app's single public entry point.

Every mutation in the theme app (and any future app) that appears on a
"must be audited" list calls `record()` inside the same transaction as the
change it describes — see docs/security/audit.md.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.http import HttpRequest

from apps.audit.models import AuditLog
from apps.core.middleware import get_current_request_id


def record(
    *,
    actor: models.Model | None,
    action: str,
    entity: models.Model,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str = "",
    request: HttpRequest | None = None,
) -> AuditLog:
    entity_id = str(getattr(entity, "public_id", entity.pk))
    ip_address = request.META.get("REMOTE_ADDR") if request is not None else None

    return AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=type(entity).__name__,
        entity_id=entity_id,
        before=before,
        after=after,
        reason=reason,
        ip_address=ip_address,
        correlation_id=get_current_request_id(),
    )
