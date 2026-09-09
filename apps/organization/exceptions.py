"""Domain exceptions for the organization app."""


class OrganizationError(Exception):
    """Base class for organization domain errors."""


class OrganizationValidationError(OrganizationError):
    """Raised when a service-level business rule fails (distinct from Django
    form/model ValidationError, which cover field-shape validation)."""
