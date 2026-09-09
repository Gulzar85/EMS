import pytest

from apps.theme import selectors
from apps.theme.models import ThemeVersion
from apps.theme.tests.factories import ThemeFactory, ThemeVersionFactory

pytestmark = pytest.mark.django_db


def test_get_active_theme_returns_none_when_none_active():
    ThemeFactory(is_active=False)
    assert selectors.get_active_theme() is None


def test_get_active_theme_returns_the_active_one():
    ThemeFactory(is_active=False)
    active = ThemeFactory(is_active=True)
    assert selectors.get_active_theme() == active


def test_get_themes_for_list_filters_by_name():
    ThemeFactory(name="Holiday Promo")
    ThemeFactory(name="Default Theme")
    results = list(selectors.get_themes_for_list(q="holiday"))
    assert len(results) == 1
    assert results[0].name == "Holiday Promo"


def test_get_themes_for_list_annotates_version_count():
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1)
    ThemeVersionFactory(theme=theme, version_number=2)
    result = selectors.get_themes_for_list().get(pk=theme.pk)
    assert result.version_count == 2


def test_get_draft_version_returns_latest_draft():
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    draft = ThemeVersionFactory(theme=theme, version_number=2, status=ThemeVersion.Status.DRAFT)
    assert selectors.get_draft_version(theme) == draft


def test_get_draft_version_returns_none_if_fully_published():
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    assert selectors.get_draft_version(theme) is None


def test_get_published_versions_excludes_drafts():
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    ThemeVersionFactory(theme=theme, version_number=2, status=ThemeVersion.Status.DRAFT)
    published = list(selectors.get_published_versions(theme))
    assert len(published) == 1
    assert published[0].version_number == 1
