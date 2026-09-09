"""Domain exceptions for the theme app — used by views to distinguish
"bad input" from "not allowed" from "business conflict" (see
docs/development/coding-standards.md)."""


class ThemeError(Exception):
    """Base class for theme domain errors."""


class ThemeValidationError(ThemeError):
    """Raised when theme token data fails schema/security validation."""


class ThemeVersionImmutableError(ThemeError):
    """Raised when code attempts to modify an already-published version."""
