from django.apps import AppConfig


class ThemeConfig(AppConfig):
    """Reserved for Phase 02 (Dynamic Theme Engine).

    Deliberately empty in Phase 01: no ThemeConfiguration model, no views.
    Registering the app now means Phase 02 only has to add files here, not
    re-scaffold the app. See docs/architecture/theme-architecture.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.theme"
    label = "theme"
    verbose_name = "Theme"
