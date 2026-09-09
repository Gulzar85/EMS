"""Small shared vocabulary for the employees app — kept out of models.py so
services/selectors/forms can import it without a model-layer dependency.
"""

from __future__ import annotations

# EmployeeEmployment.status values that mean "this person currently has a
# live employment relationship, whether or not they're actively working
# right now" — used to compute Employee.is_active without a second,
# independently-editable boolean field (see docs/adr/ADR-020).
CURRENTLY_EMPLOYED_STATUSES = frozenset({"probation", "active", "on_leave", "suspended"})

# Terminal states — once here, an employment period never re-opens. A
# rehire is a documented future extension (see docs/adr/ADR-020), not
# something this phase's lifecycle service attempts.
TERMINAL_EMPLOYMENT_STATUSES = frozenset({"resigned", "terminated", "retired"})
