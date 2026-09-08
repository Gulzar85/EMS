"""
Production settings.

See docs/architecture/deployment-architecture.md and
docs/security/authentication.md for the full rationale behind these values.
"""

from .base import *  # noqa: F403
from .base import BASE_DIR, LOGGING, env  # noqa: F401

DEBUG = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Structured JSON logs in production (see apps/core/logging.py).
LOGGING["handlers"]["console"]["formatter"] = "json"

# ---------------------------------------------------------------------------
# Future hook points — intentionally NOT implemented in Phase 01.
# ---------------------------------------------------------------------------
#
# Error tracking (Sentry): reserve SENTRY_DSN as an env var. When adopted,
# add the `sentry-sdk` dependency and initialize it here, scrubbing PII
# (salary, national ID, etc.) per docs/security/authorization.md before any
# event is sent.
#
# SENTRY_DSN = env("SENTRY_DSN", default=None)
#
# Media storage (Azure Blob / S3-compatible): swapping local filesystem
# storage for cloud storage is a `STORAGES["default"]` setting change using
# django-storages — not a code change — once that dependency is justified.
#
# STORAGES = {
#     "default": {"BACKEND": "storages.backends.azure_storage.AzureStorage"},
#     "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
# }
