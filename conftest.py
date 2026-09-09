import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """LocMemCache (config/settings/test.py) persists for the whole pytest
    session, not per-test. Several apps cache scope/lookup data keyed by
    database row ids (e.g. apps.organization.permissions' organization-unit
    parent map) — since each `@pytest.mark.django_db` test rolls back its
    own transaction but Postgres sequences keep incrementing regardless,
    a later test's freshly-created rows can reuse ids a stale cache entry
    from an earlier test still describes, silently corrupting results
    instead of raising. Clearing the cache before and after every test
    closes that gap project-wide (apps/theme/tests/conftest.py already did
    this locally for theme-specific caching; this generalizes it).
    """
    cache.clear()
    yield
    cache.clear()
