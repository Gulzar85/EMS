"""Development settings — never used in production."""

from .base import *  # noqa: F403
from .base import env

DEBUG = True

# Local HTTP is fine in dev; production.py turns these on.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# Verbose, human-readable console logging in dev.
LOGGING["loggers"]["ems"]["level"] = "DEBUG"  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]
