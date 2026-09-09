from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.theme.views import AppearanceUpdateView, theme_css_view

urlpatterns = [
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),
    path("theme.css", theme_css_view, name="theme-css"),
    path("settings/themes/", include("apps.theme.urls")),
    path("preferences/appearance/", AppearanceUpdateView.as_view(), name="appearance-update"),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "apps.core.views.custom_400"
handler403 = "apps.core.views.custom_403"
handler404 = "apps.core.views.custom_404"
handler500 = "apps.core.views.custom_500"
