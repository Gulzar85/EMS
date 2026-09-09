import pytest
from django.db import IntegrityError, transaction

from apps.theme.exceptions import ThemeVersionImmutableError
from apps.theme.models import Theme, ThemeVersion
from apps.theme.tests.factories import ThemeFactory, ThemeVersionFactory

pytestmark = pytest.mark.django_db


def test_only_one_theme_can_be_active():
    ThemeFactory(is_active=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ThemeFactory(is_active=True)


def test_inactive_themes_are_unrestricted():
    ThemeFactory(is_active=False)
    ThemeFactory(is_active=False)  # must not raise
    assert Theme.objects.filter(is_active=False).count() == 2


def test_activating_a_second_theme_requires_deactivating_the_first():
    # Direct proof that the DB constraint — not just application logic —
    # is what prevents two active themes (Phase 02 plan §3, §8).
    first = ThemeFactory(is_active=True)
    second = ThemeFactory(is_active=False)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            second.is_active = True
            second.save(update_fields=["is_active"])

    first.refresh_from_db()
    assert first.is_active is True


def test_version_number_unique_per_theme():
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ThemeVersionFactory(theme=theme, version_number=1)


def test_same_version_number_allowed_across_different_themes():
    ThemeVersionFactory(theme=ThemeFactory(), version_number=1)
    ThemeVersionFactory(theme=ThemeFactory(), version_number=1)  # must not raise


def test_published_version_tokens_are_immutable():
    version = ThemeVersionFactory(status=ThemeVersion.Status.PUBLISHED)
    version.tokens = {**version.tokens, "schema_version": 999}
    with pytest.raises(ThemeVersionImmutableError):
        version.save()


def test_published_version_status_cannot_revert_to_draft():
    version = ThemeVersionFactory(status=ThemeVersion.Status.PUBLISHED)
    version.status = ThemeVersion.Status.DRAFT
    with pytest.raises(ThemeVersionImmutableError):
        version.save()


def test_draft_version_can_still_be_edited():
    version = ThemeVersionFactory(status=ThemeVersion.Status.DRAFT)
    version.tokens = {**version.tokens, "schema_version": 1}
    version.save()  # must not raise
