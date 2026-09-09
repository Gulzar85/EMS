"""A tiny shared lookup used by every non-generic employee CBV (lifecycle,
assignment, history, profile) — kept here instead of duplicated per module,
since it's the same object-level-scoped fetch every one of them needs.
"""

from __future__ import annotations

from django.http import Http404

from apps.employees import selectors
from apps.employees.models import Employee


def _get_employee_or_404(user, public_id) -> Employee:
    employee = selectors.get_employee_by_public_id(public_id, user)
    if employee is None:
        raise Http404("Employee not found.")
    return employee
