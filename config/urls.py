from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core.views import ErrorView
from apps.theme.views import AppearanceUpdateView, ThemeCSSView

urlpatterns = [
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),
    path("theme.css", ThemeCSSView.as_view(), name="theme-css"),
    path("settings/themes/", include("apps.theme.urls")),
    path("organization/", include("apps.organization.urls")),
    path("preferences/appearance/", AppearanceUpdateView.as_view(), name="appearance-update"),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = ErrorView.as_view(template_name="pages/errors/400.html", status_code=400)
handler403 = ErrorView.as_view(template_name="pages/errors/403.html", status_code=403)
handler404 = ErrorView.as_view(template_name="pages/errors/404.html", status_code=404)
handler500 = ErrorView.as_view(template_name="pages/errors/500.html", status_code=500)
