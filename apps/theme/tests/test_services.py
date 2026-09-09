import copy

import pytest
from django.core.cache import cache
from django.test import TransactionTestCase

from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditLog
from apps.theme import services
from apps.theme.exceptions import ThemeValidationError
from apps.theme.models import Theme, ThemeVersion
from apps.theme.tests.factories import ThemeFactory, ThemeVersionFactory
from apps.theme.validation import DEFAULT_THEME_TOKENS

pytestmark = pytest.mark.django_db


def test_create_theme_creates_theme_and_first_draft_version():
    actor = UserFactory()
    theme = services.create_theme(name="Holiday Promo", description="Red and green", actor=actor)

    assert theme.name == "Holiday Promo"
    assert theme.created_by == actor
    draft = theme.versions.get()
    assert draft.version_number == 1
    assert draft.status == ThemeVersion.Status.DRAFT
    assert draft.tokens == DEFAULT_THEME_TOKENS
    assert AuditLog.objects.filter(action="theme.created", entity_id=str(theme.public_id)).exists()


def test_update_draft_tokens_creates_a_draft_if_none_exists():
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    new_tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    new_tokens["colors"]["brand"] = {"light": "#0057b8", "dark": "#0057b8"}

    draft = services.update_draft_tokens(theme=theme, tokens=new_tokens, actor=None)

    assert draft.version_number == 2
    assert draft.status == ThemeVersion.Status.DRAFT
    assert draft.tokens["colors"]["brand"]["light"] == "#0057b8"


def test_update_draft_tokens_updates_existing_draft_in_place():
    theme = ThemeFactory()
    draft = ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.DRAFT)
    new_tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    new_tokens["typography"]["font_size_base"] = "18px"

    updated = services.update_draft_tokens(theme=theme, tokens=new_tokens, actor=None)

    assert updated.pk == draft.pk  # same row, not a new version
    assert theme.versions.count() == 1


def test_update_draft_tokens_rejects_invalid_tokens():
    theme = ThemeFactory()
    with pytest.raises(ThemeValidationError):
        services.update_draft_tokens(theme=theme, tokens={"not": "valid"}, actor=None)
    assert theme.versions.count() == 0  # nothing was written


def test_publish_theme_makes_version_immutable_and_theme_active():
    theme = ThemeFactory(is_active=False)
    draft = ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.DRAFT)
    actor = UserFactory()

    published = services.publish_theme(theme=theme, version=draft, actor=actor, reason="go live")

    assert published.status == ThemeVersion.Status.PUBLISHED
    assert published.published_by == actor
    assert published.published_at is not None
    theme.refresh_from_db()
    assert theme.is_active is True
    assert theme.active_version_id == published.pk
    assert AuditLog.objects.filter(action="theme.published", reason="go live").exists()


def test_publish_theme_deactivates_previously_active_theme():
    old_active = ThemeFactory(is_active=True)
    new_theme = ThemeFactory(is_active=False)
    draft = ThemeVersionFactory(theme=new_theme, version_number=1, status=ThemeVersion.Status.DRAFT)

    services.publish_theme(theme=new_theme, version=draft, actor=None)

    old_active.refresh_from_db()
    assert old_active.is_active is False


def test_publish_theme_rejects_already_published_version():
    theme = ThemeFactory()
    version = ThemeVersionFactory(
        theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED
    )
    with pytest.raises(ThemeValidationError):
        services.publish_theme(theme=theme, version=version, actor=None)


def test_rollback_theme_repoints_active_version():
    theme = ThemeFactory(is_active=True)
    v1 = ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    v2 = ThemeVersionFactory(theme=theme, version_number=2, status=ThemeVersion.Status.PUBLISHED)
    theme.active_version = v2
    theme.save(update_fields=["active_version"])

    services.rollback_theme(theme=theme, target_version=v1, actor=None, reason="oops")

    theme.refresh_from_db()
    assert theme.active_version_id == v1.pk
    assert ThemeVersion.objects.get(pk=v2.pk).status == ThemeVersion.Status.PUBLISHED  # untouched
    assert AuditLog.objects.filter(action="theme.rolled_back", reason="oops").exists()


def test_rollback_theme_rejects_draft_target():
    theme = ThemeFactory()
    draft = ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.DRAFT)
    with pytest.raises(ThemeValidationError):
        services.rollback_theme(theme=theme, target_version=draft, actor=None)


def test_activate_theme_switches_the_active_flag():
    old_active = ThemeFactory(is_active=True)
    new_theme = ThemeFactory(is_active=False)
    ThemeVersionFactory(theme=new_theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    new_theme.active_version = new_theme.versions.get()
    new_theme.save(update_fields=["active_version"])

    services.activate_theme(theme=new_theme, actor=None)

    old_active.refresh_from_db()
    new_theme.refresh_from_db()
    assert old_active.is_active is False
    assert new_theme.is_active is True


def test_activate_theme_rejects_theme_with_no_published_version():
    theme = ThemeFactory(is_active=False)
    with pytest.raises(ThemeValidationError):
        services.activate_theme(theme=theme, actor=None)


def test_duplicate_theme_copies_active_version_tokens_into_new_draft():
    source = ThemeFactory(is_active=True)
    tokens = copy.deepcopy(DEFAULT_THEME_TOKENS)
    tokens["colors"]["brand"] = {"light": "#123456", "dark": "#123456"}
    version = ThemeVersionFactory(
        theme=source, version_number=1, status=ThemeVersion.Status.PUBLISHED, tokens=tokens
    )
    source.active_version = version
    source.save(update_fields=["active_version"])

    duplicate = services.duplicate_theme(theme=source, actor=None, new_name="Copy of source")

    assert duplicate.name == "Copy of source"
    draft = duplicate.versions.get()
    assert draft.status == ThemeVersion.Status.DRAFT
    assert draft.tokens["colors"]["brand"]["light"] == "#123456"
    assert duplicate.is_active is False  # duplicating never affects live state


def test_delete_theme_refuses_the_active_theme():
    theme = ThemeFactory(is_active=True)
    with pytest.raises(ThemeValidationError):
        services.delete_theme(theme=theme, actor=None)
    assert Theme.objects.filter(pk=theme.pk).exists()


def test_delete_theme_removes_inactive_theme_and_its_versions():
    theme = ThemeFactory(is_active=False)
    ThemeVersionFactory(theme=theme, version_number=1)
    theme_pk = theme.pk

    services.delete_theme(theme=theme, actor=None)

    assert not Theme.objects.filter(pk=theme_pk).exists()
    assert not ThemeVersion.objects.filter(theme_id=theme_pk).exists()
    assert AuditLog.objects.filter(action="theme.deleted").exists()


class ThemeCacheInvalidationTests(TransactionTestCase):
    """transaction.on_commit() callbacks never fire inside the implicit
    atomic wrapper Django's plain TestCase uses — TransactionTestCase is
    required to actually observe post-commit cache invalidation
    (Phase 02 plan's testing section calls this out explicitly)."""

    def setUp(self):
        # See apps/theme/tests/conftest.py — the same seeded-active-theme
        # concern applies here, but TransactionTestCase doesn't reliably
        # pick up the pytest autouse fixture, so clear explicitly.
        Theme.objects.all().delete()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_publish_invalidates_the_active_tokens_cache(self):
        theme = ThemeFactory(is_active=False)
        draft = ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.DRAFT)

        assert (
            services.ThemeCacheService.get_active_tokens() is None
        )  # populate cache with "nothing active"

        services.publish_theme(theme=theme, version=draft, actor=None)

        tokens = services.ThemeCacheService.get_active_tokens()
        assert tokens is not None
        assert tokens == draft.tokens
