"""Shared hierarchy validation.

Three models in this app have a self-referential "next node up" pointer
that must never form a cycle: OrganizationUnit.parent, Department.parent,
and Position.reports_to. Three call sites justify one small shared
function — not a generic hierarchy framework (Phase 03 plan §95, judgment
call #10).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Model


def assert_no_cycle(
    node: Model, candidate: Model | None, *, parent_attr: str, field_name: str
) -> None:
    """Raise ValidationError if setting `node.<parent_attr> = candidate` would
    create a cycle (candidate is node itself, or candidate descends from node).
    """
    if candidate is None:
        return

    if node.pk is not None and candidate.pk == node.pk:
        raise ValidationError({field_name: f"A record cannot be its own {field_name}."})

    seen: set = set()
    current = candidate
    while current is not None:
        if node.pk is not None and current.pk == node.pk:
            raise ValidationError(
                {field_name: f"This change would create a circular {field_name} relationship."}
            )
        if current.pk in seen:
            break  # already-corrupt data upstream — stop rather than loop forever
        seen.add(current.pk)
        current = getattr(current, parent_attr)
