"""Domain exceptions for the employees app."""


class EmployeeError(Exception):
    """Base class for employee domain errors."""


class EmployeeValidationError(EmployeeError):
    """Raised when a service-level business rule fails (distinct from Django
    form/model ValidationError, which cover field-shape validation)."""
