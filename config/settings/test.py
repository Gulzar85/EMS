"""Settings used by pytest (DJANGO_SETTINGS_MODULE, see pyproject.toml)."""

from .base import *  # noqa: F403

DEBUG = False

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

AXES_ENABLED = False

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["ems"]["level"] = "WARNING"  # noqa: F405
