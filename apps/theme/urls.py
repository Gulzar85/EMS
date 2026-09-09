from django.urls import path

from apps.theme import views

app_name = "theme"

urlpatterns = [
    path("", views.ThemeListView.as_view(), name="list"),
    path("create/", views.ThemeCreateView.as_view(), name="create"),
    path("styleguide/", views.StyleguideView.as_view(), name="styleguide"),
    path("<uuid:public_id>/", views.ThemeDetailView.as_view(), name="detail"),
    path("<uuid:public_id>/edit/", views.ThemeUpdateView.as_view(), name="update"),
    path("<uuid:public_id>/studio/", views.ThemeStudioView.as_view(), name="studio"),
    path("<uuid:public_id>/preview/", views.ThemePreviewView.as_view(), name="preview"),
    path("<uuid:public_id>/publish/", views.ThemePublishView.as_view(), name="publish"),
    path("<uuid:public_id>/rollback/", views.ThemeRollbackView.as_view(), name="rollback"),
    path("<uuid:public_id>/activate/", views.ThemeActivateView.as_view(), name="activate"),
    path("<uuid:public_id>/duplicate/", views.ThemeDuplicateView.as_view(), name="duplicate"),
    path("<uuid:public_id>/delete/", views.ThemeDeleteView.as_view(), name="delete"),
]
