import pytest
from django.core.cache import cache

from apps.theme.models import Theme


@pytest.fixture(autouse=True)
def _clear_seeded_theme(db):
    """The 0002_seed_default_theme data migration seeds one active Theme in
    every database, including the test database — tests that set up their
    own is_active=True theme would otherwise collide with it under the
    theme_single_active constraint. Start every theme test from a clean
    slate instead.
    """
    Theme.objects.all().delete()


@pytest.fixture(autouse=True)
def _clear_theme_cache():
    # LocMemCache (config/settings/test.py) persists for the whole test
    # session, not per-test — without this, ThemeCacheService's cached
    # "no active theme" (or a stale theme's) result leaks across tests.
    cache.clear()
    yield
    cache.clear()
