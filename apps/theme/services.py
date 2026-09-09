"""Theme business operations.

Every function here: validates -> transaction.atomic() (+ select_for_update()
for anything touching "which theme/version is active") -> writes -> audit
-> (where the change affects live state) transaction.on_commit(cache
invalidation). Views call these; they never write to Theme/ThemeVersion
directly. See docs/development/theme-development.md.
"""

from __future__ import annotations

from django.core.cache import cache
from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
from apps.audit.services import record as record_audit
from apps.theme.exceptions import ThemeValidationError
from apps.theme.models import Theme, ThemeVersion
from apps.theme.selectors import get_draft_version
from apps.theme.validation import DEFAULT_THEME_TOKENS, validate_theme_tokens

_ACTIVE_TOKENS_CACHE_KEY = "theme:active:tokens"
_ACTIVE_TOKENS_CACHE_TIMEOUT = 60 * 60 * 24  # 24h; explicitly invalidated on any mutation anyway
_CACHE_MISS = object()


class ThemeCacheService:
    """Cache-aside on the single active theme's tokens + version id.

    Bundled into one cache entry (rather than two) so the common per-request
    reads — the /theme.css body and the cache-busting version id used by the
    {% theme_css_url %} template tag — cost one cache read, not two, and
    never disagree with each other between a publish and its invalidation.
    """

    @classmethod
    def _get_active(cls) -> dict:
        cached = cache.get(_ACTIVE_TOKENS_CACHE_KEY, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached

        from apps.theme.selectors import (
            get_active_theme,  # local import avoids a cycle at module load
        )

        theme = get_active_theme()
        if theme and theme.active_version_id:
            result = {"version_id": theme.active_version_id, "tokens": theme.active_version.tokens}
        else:
            result = {"version_id": None, "tokens": None}
        cache.set(_ACTIVE_TOKENS_CACHE_KEY, result, _ACTIVE_TOKENS_CACHE_TIMEOUT)
        return result

    @classmethod
    def get_active_tokens(cls) -> dict | None:
        return cls._get_active()["tokens"]

    @classmethod
    def get_active_version_id(cls) -> int | None:
        return cls._get_active()["version_id"]

    @classmethod
    def invalidate(cls) -> None:
        cache.delete(_ACTIVE_TOKENS_CACHE_KEY)


def _next_version_number(theme: Theme) -> int:
    return (theme.versions.aggregate(Max("version_number"))["version_number__max"] or 0) + 1


def _set_active(theme: Theme, actor: User | None) -> None:
    """Must be called from inside a transaction that already holds
    select_for_update() on the relevant Theme rows."""
    Theme.objects.filter(is_active=True).exclude(pk=theme.pk).update(is_active=False)
    theme.is_active = True
    theme.save(update_fields=["is_active"])


@transaction.atomic
def create_theme(*, name: str, description: str, actor: User | None) -> Theme:
    theme = Theme.objects.create(name=name, description=description, created_by=actor)
    ThemeVersion.objects.create(
        theme=theme,
        version_number=1,
        status=ThemeVersion.Status.DRAFT,
        tokens=DEFAULT_THEME_TOKENS,
        created_by=actor,
    )
    record_audit(actor=actor, action="theme.created", entity=theme, after={"name": name})
    return theme


@transaction.atomic
def update_draft_tokens(*, theme: Theme, tokens: dict, actor: User | None) -> ThemeVersion:
    validate_theme_tokens(tokens)

    draft = get_draft_version(theme)
    if draft is None:
        draft = ThemeVersion.objects.create(
            theme=theme,
            version_number=_next_version_number(theme),
            status=ThemeVersion.Status.DRAFT,
            tokens=tokens,
            created_by=actor,
        )
        record_audit(
            actor=actor, action="theme.draft_created", entity=draft, after={"tokens": tokens}
        )
    else:
        before = draft.tokens
        draft.tokens = tokens
        draft.save(update_fields=["tokens", "updated_at"])
        record_audit(
            actor=actor,
            action="theme.updated",
            entity=draft,
            before={"tokens": before},
            after={"tokens": tokens},
        )
    return draft


@transaction.atomic
def publish_theme(
    *, theme: Theme, version: ThemeVersion, actor: User | None, reason: str = ""
) -> ThemeVersion:
    from django.utils import timezone

    theme = Theme.objects.select_for_update().get(pk=theme.pk)
    version = ThemeVersion.objects.select_for_update().get(pk=version.pk, theme=theme)

    if version.status == ThemeVersion.Status.PUBLISHED:
        raise ThemeValidationError("This version is already published.")
    validate_theme_tokens(version.tokens)

    version.status = ThemeVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.published_by = actor
    version.save(update_fields=["status", "published_at", "published_by", "updated_at"])

    theme.active_version = version
    theme.save(update_fields=["active_version"])
    _set_active(theme, actor)

    record_audit(
        actor=actor,
        action="theme.published",
        entity=version,
        after={"version_number": version.version_number},
        reason=reason,
    )
    transaction.on_commit(ThemeCacheService.invalidate)
    return version


@transaction.atomic
def rollback_theme(
    *, theme: Theme, target_version: ThemeVersion, actor: User | None, reason: str = ""
) -> Theme:
    theme = Theme.objects.select_for_update().get(pk=theme.pk)
    target_version = ThemeVersion.objects.select_for_update().get(pk=target_version.pk, theme=theme)

    if target_version.status != ThemeVersion.Status.PUBLISHED:
        raise ThemeValidationError("Can only roll back to a published version.")

    before_version_id = theme.active_version_id
    theme.active_version = target_version
    theme.save(update_fields=["active_version"])

    record_audit(
        actor=actor,
        action="theme.rolled_back",
        entity=theme,
        before={"active_version_id": before_version_id},
        after={
            "active_version_id": target_version.id,
            "version_number": target_version.version_number,
        },
        reason=reason,
    )
    transaction.on_commit(ThemeCacheService.invalidate)
    return theme


@transaction.atomic
def activate_theme(*, theme: Theme, actor: User | None) -> Theme:
    theme = Theme.objects.select_for_update().get(pk=theme.pk)
    if theme.active_version_id is None:
        raise ThemeValidationError("This theme has no published version to activate.")

    _set_active(theme, actor)
    record_audit(actor=actor, action="theme.activated", entity=theme)
    transaction.on_commit(ThemeCacheService.invalidate)
    return theme


@transaction.atomic
def duplicate_theme(*, theme: Theme, actor: User | None, new_name: str) -> Theme:
    source_version = theme.active_version or get_draft_version(theme)
    source_tokens = source_version.tokens if source_version else DEFAULT_THEME_TOKENS

    new_theme = Theme.objects.create(
        name=new_name, description=f"Duplicated from {theme.name}", created_by=actor
    )
    ThemeVersion.objects.create(
        theme=new_theme,
        version_number=1,
        status=ThemeVersion.Status.DRAFT,
        tokens=source_tokens,
        created_by=actor,
    )
    record_audit(
        actor=actor,
        action="theme.duplicated",
        entity=new_theme,
        after={"source_theme": str(theme.public_id)},
    )
    return new_theme


@transaction.atomic
def delete_theme(*, theme: Theme, actor: User | None) -> None:
    if theme.is_active:
        raise ThemeValidationError("Cannot delete the active theme. Activate another theme first.")

    snapshot = {"name": theme.name, "version_count": theme.versions.count()}
    record_audit(actor=actor, action="theme.deleted", entity=theme, before=snapshot)
    theme.delete()
