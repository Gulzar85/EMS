from django.urls import path

from apps.employees import views

app_name = "employees"

urlpatterns = [
    path("dashboard/", views.EmployeeDashboardView.as_view(), name="dashboard"),
    path("me/", views.MyProfileView.as_view(), name="my-profile"),
    path("", views.EmployeeListView.as_view(), name="employee-list"),
    path("create/", views.EmployeeCreateView.as_view(), name="employee-create"),
    path("<uuid:public_id>/", views.EmployeeDetailView.as_view(), name="employee-detail"),
    path("<uuid:public_id>/edit/", views.EmployeeUpdateView.as_view(), name="employee-update"),
    path("<uuid:public_id>/delete/", views.EmployeeDeleteView.as_view(), name="employee-delete"),
    path("<uuid:public_id>/history/", views.EmployeeHistoryView.as_view(), name="employee-history"),
    path(
        "<uuid:public_id>/activate/", views.EmployeeActivateView.as_view(), name="employee-activate"
    ),
    path("<uuid:public_id>/confirm/", views.EmployeeConfirmView.as_view(), name="employee-confirm"),
    path(
        "<uuid:public_id>/place-on-leave/",
        views.EmployeePlaceOnLeaveView.as_view(),
        name="employee-place-on-leave",
    ),
    path(
        "<uuid:public_id>/return-from-leave/",
        views.EmployeeReturnFromLeaveView.as_view(),
        name="employee-return-from-leave",
    ),
    path("<uuid:public_id>/suspend/", views.EmployeeSuspendView.as_view(), name="employee-suspend"),
    path(
        "<uuid:public_id>/reinstate/",
        views.EmployeeReinstateView.as_view(),
        name="employee-reinstate",
    ),
    path(
        "<uuid:public_id>/deactivate/",
        views.EmployeeDeactivateView.as_view(),
        name="employee-deactivate",
    ),
    path(
        "<uuid:public_id>/assign-position/",
        views.EmployeeAssignmentCreateView.as_view(),
        name="employee-assignment-create",
    ),
    path(
        "<uuid:public_id>/change-position/",
        views.EmployeeAssignmentUpdateView.as_view(),
        name="employee-assignment-update",
    ),
    path(
        "<uuid:public_id>/assignments/<int:assignment_id>/end/",
        views.EmployeeAssignmentEndView.as_view(),
        name="employee-assignment-end",
    ),
    path(
        "<uuid:public_id>/change-manager/",
        views.EmployeeManagerAssignmentView.as_view(),
        name="employee-manager-assignment",
    ),
    path(
        "<uuid:public_id>/link-user/",
        views.EmployeeUserLinkView.as_view(),
        name="employee-user-link",
    ),
    path(
        "<uuid:public_id>/unlink-user/",
        views.EmployeeUserUnlinkView.as_view(),
        name="employee-user-unlink",
    ),
]
