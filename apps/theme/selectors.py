"""Reusable read queries for the theme app.

Plain single-row lookups (Theme.objects.get(pk=...)) stay inline in views —
these exist because they're either reused across multiple call sites or
carry query-shape decisions (select_related, ordering) worth centralizing.
"""

from __future__ import annotations

from django.db.models import Count, QuerySet

from apps.theme.models import Theme, ThemeVersion


def get_active_theme() -> Theme | None:
    return Theme.objects.select_related("active_version").filter(is_active=True).first()


def get_themes_for_list(q: str = "") -> QuerySet[Theme]:
    # annotate() the version count here rather than calling theme.versions.count()
    # per-row in the template — avoids an N+1 on the list page.
    qs = (
        Theme.objects.select_related("active_version")
        .annotate(version_count=Count("versions"))
        .order_by("name")
    )
    if q:
        qs = qs.filter(name__icontains=q)
    return qs


def get_theme_versions(theme: Theme) -> QuerySet[ThemeVersion]:
    return theme.versions.order_by("-version_number")


def get_published_versions(theme: Theme) -> QuerySet[ThemeVersion]:
    return theme.versions.filter(status=ThemeVersion.Status.PUBLISHED).order_by("-version_number")


def get_draft_version(theme: Theme) -> ThemeVersion | None:
    return (
        theme.versions.filter(status=ThemeVersion.Status.DRAFT).order_by("-version_number").first()
    )
