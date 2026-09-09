from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("health/", views.HealthView.as_view(), name="health"),
    path("health/live/", views.HealthLiveView.as_view(), name="health-live"),
    path("health/ready/", views.HealthReadyView.as_view(), name="health-ready"),
]
