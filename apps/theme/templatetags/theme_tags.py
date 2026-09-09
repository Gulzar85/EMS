from django import template
from django.urls import reverse

from apps.theme.services import ThemeCacheService

register = template.Library()


@register.simple_tag
def theme_css_url() -> str:
    """The public /theme.css URL, cache-busted with the active version's id
    so a publish/rollback is picked up immediately rather than waiting on a
    stale browser/CDN cache of the previous URL."""
    version_id = ThemeCacheService.get_active_version_id() or 0
    return f"{reverse('theme-css')}?v={version_id}"
