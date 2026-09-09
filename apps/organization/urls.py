from django.urls import path

from apps.organization import views

app_name = "organization"

urlpatterns = [
    path("", views.OrganizationDashboardView.as_view(), name="dashboard"),
    path(
        "units/<uuid:public_id>/children/",
        views.OrganizationUnitChildrenView.as_view(),
        name="unit-children",
    ),
    path("units/", views.OrganizationUnitListView.as_view(), name="unit-list"),
    path("units/create/", views.OrganizationUnitCreateView.as_view(), name="unit-create"),
    path("units/<uuid:public_id>/", views.OrganizationUnitDetailView.as_view(), name="unit-detail"),
    path(
        "units/<uuid:public_id>/edit/",
        views.OrganizationUnitUpdateView.as_view(),
        name="unit-update",
    ),
    path(
        "units/<uuid:public_id>/delete/",
        views.OrganizationUnitDeleteView.as_view(),
        name="unit-delete",
    ),
    path("locations/", views.LocationListView.as_view(), name="location-list"),
    path("locations/create/", views.LocationCreateView.as_view(), name="location-create"),
    path("locations/<uuid:public_id>/", views.LocationDetailView.as_view(), name="location-detail"),
    path(
        "locations/<uuid:public_id>/edit/",
        views.LocationUpdateView.as_view(),
        name="location-update",
    ),
    path(
        "locations/<uuid:public_id>/delete/",
        views.LocationDeleteView.as_view(),
        name="location-delete",
    ),
    path("restaurants/", views.RestaurantListView.as_view(), name="restaurant-list"),
    path("restaurants/create/", views.RestaurantCreateView.as_view(), name="restaurant-create"),
    path(
        "restaurants/<uuid:public_id>/",
        views.RestaurantDetailView.as_view(),
        name="restaurant-detail",
    ),
    path(
        "restaurants/<uuid:public_id>/edit/",
        views.RestaurantUpdateView.as_view(),
        name="restaurant-update",
    ),
    path(
        "restaurants/<uuid:public_id>/delete/",
        views.RestaurantDeleteView.as_view(),
        name="restaurant-delete",
    ),
    path("departments/", views.DepartmentListView.as_view(), name="department-list"),
    path("departments/create/", views.DepartmentCreateView.as_view(), name="department-create"),
    path(
        "departments/<uuid:public_id>/",
        views.DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    path(
        "departments/<uuid:public_id>/edit/",
        views.DepartmentUpdateView.as_view(),
        name="department-update",
    ),
    path(
        "departments/<uuid:public_id>/delete/",
        views.DepartmentDeleteView.as_view(),
        name="department-delete",
    ),
    path("job-families/", views.JobFamilyListView.as_view(), name="job-family-list"),
    path("job-families/create/", views.JobFamilyCreateView.as_view(), name="job-family-create"),
    path(
        "job-families/<uuid:public_id>/",
        views.JobFamilyDetailView.as_view(),
        name="job-family-detail",
    ),
    path(
        "job-families/<uuid:public_id>/edit/",
        views.JobFamilyUpdateView.as_view(),
        name="job-family-update",
    ),
    path(
        "job-families/<uuid:public_id>/delete/",
        views.JobFamilyDeleteView.as_view(),
        name="job-family-delete",
    ),
    path("job-levels/", views.JobLevelListView.as_view(), name="job-level-list"),
    path("job-levels/create/", views.JobLevelCreateView.as_view(), name="job-level-create"),
    path(
        "job-levels/<uuid:public_id>/", views.JobLevelDetailView.as_view(), name="job-level-detail"
    ),
    path(
        "job-levels/<uuid:public_id>/edit/",
        views.JobLevelUpdateView.as_view(),
        name="job-level-update",
    ),
    path(
        "job-levels/<uuid:public_id>/delete/",
        views.JobLevelDeleteView.as_view(),
        name="job-level-delete",
    ),
    path("jobs/", views.JobListView.as_view(), name="job-list"),
    path("jobs/create/", views.JobCreateView.as_view(), name="job-create"),
    path("jobs/<uuid:public_id>/", views.JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:public_id>/edit/", views.JobUpdateView.as_view(), name="job-update"),
    path("jobs/<uuid:public_id>/delete/", views.JobDeleteView.as_view(), name="job-delete"),
    path("positions/", views.PositionListView.as_view(), name="position-list"),
    path("positions/create/", views.PositionCreateView.as_view(), name="position-create"),
    path("positions/<uuid:public_id>/", views.PositionDetailView.as_view(), name="position-detail"),
    path(
        "positions/<uuid:public_id>/edit/",
        views.PositionUpdateView.as_view(),
        name="position-update",
    ),
    path(
        "positions/<uuid:public_id>/delete/",
        views.PositionDeleteView.as_view(),
        name="position-delete",
    ),
    path(
        "positions/<uuid:public_id>/activate/",
        views.PositionActivateView.as_view(),
        name="position-activate",
    ),
    path(
        "positions/<uuid:public_id>/deactivate/",
        views.PositionDeactivateView.as_view(),
        name="position-deactivate",
    ),
    path(
        "positions/<uuid:public_id>/freeze/",
        views.PositionFreezeView.as_view(),
        name="position-freeze",
    ),
    path(
        "positions/<uuid:public_id>/unfreeze/",
        views.PositionUnfreezeView.as_view(),
        name="position-unfreeze",
    ),
    path(
        "positions/<uuid:public_id>/duplicate/",
        views.PositionDuplicateView.as_view(),
        name="position-duplicate",
    ),
]
