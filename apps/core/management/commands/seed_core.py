"""Creates safe, obviously-fake development data. NEVER real employee data.

Usage: python manage.py seed_core
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.models import User

DEV_SUPERUSER_EMAIL = "admin@example.local"
DEV_SUPERUSER_PASSWORD = "changeme123!"  # noqa: S105 - dev-only fixture, not a real credential


class Command(BaseCommand):
    help = "Seed local-development-only fake data (a dev superuser). Never run against production."

    def handle(self, *args, **options):
        if User.objects.filter(email=DEV_SUPERUSER_EMAIL).exists():
            self.stdout.write(
                self.style.WARNING(f"{DEV_SUPERUSER_EMAIL} already exists — skipping.")
            )
            return

        User.objects.create_superuser(
            email=DEV_SUPERUSER_EMAIL,
            password=DEV_SUPERUSER_PASSWORD,
            first_name="Dev",
            last_name="Admin",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created dev superuser {DEV_SUPERUSER_EMAIL} / {DEV_SUPERUSER_PASSWORD} "
                "(local development only — never use in a real environment)."
            )
        )
