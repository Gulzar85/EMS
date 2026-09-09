from django.contrib import admin

from apps.theme.models import Theme, ThemeVersion, UserThemePreference


class ThemeVersionInline(admin.TabularInline):
    model = ThemeVersion
    extra = 0
    fields = ["version_number", "status", "published_at", "published_by"]
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "active_version", "created_by", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    readonly_fields = ["public_id", "created_at", "updated_at"]
    inlines = [ThemeVersionInline]


@admin.register(ThemeVersion)
class ThemeVersionAdmin(admin.ModelAdmin):
    """Technical/support administration only — the real editing surface is
    Theme Studio. Published versions are immutable (enforced by the model
    itself, but the admin also hides the fields to avoid a confusing UI)."""

    list_display = ["theme", "version_number", "status", "published_at"]
    list_filter = ["status"]
    search_fields = ["theme__name"]

    def get_readonly_fields(self, request, obj=None):
        base = ["public_id", "created_at", "updated_at", "version_number", "theme"]
        if obj and obj.status == ThemeVersion.Status.PUBLISHED:
            return base + ["status", "tokens", "schema_version", "published_at", "published_by"]
        return base


@admin.register(UserThemePreference)
class UserThemePreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "appearance", "updated_at"]
    search_fields = ["user__email"]
