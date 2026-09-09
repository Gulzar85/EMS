from apps.employees.views.assignment import (
    EmployeeAssignmentCreateView,
    EmployeeAssignmentEndView,
    EmployeeAssignmentUpdateView,
    EmployeeManagerAssignmentView,
)
from apps.employees.views.dashboard import EmployeeDashboardView
from apps.employees.views.employee import (
    EmployeeCreateView,
    EmployeeDeleteView,
    EmployeeDetailView,
    EmployeeListView,
    EmployeeUpdateView,
)
from apps.employees.views.history import EmployeeHistoryView
from apps.employees.views.lifecycle import (
    EmployeeActivateView,
    EmployeeConfirmView,
    EmployeeDeactivateView,
    EmployeePlaceOnLeaveView,
    EmployeeReinstateView,
    EmployeeReturnFromLeaveView,
    EmployeeSuspendView,
)
from apps.employees.views.profile import MyProfileView
from apps.employees.views.user_link import EmployeeUserLinkView, EmployeeUserUnlinkView

__all__ = [
    "EmployeeDashboardView",
    "EmployeeListView",
    "EmployeeDetailView",
    "EmployeeCreateView",
    "EmployeeUpdateView",
    "EmployeeDeleteView",
    "EmployeeActivateView",
    "EmployeeConfirmView",
    "EmployeePlaceOnLeaveView",
    "EmployeeReturnFromLeaveView",
    "EmployeeSuspendView",
    "EmployeeReinstateView",
    "EmployeeDeactivateView",
    "EmployeeAssignmentCreateView",
    "EmployeeAssignmentUpdateView",
    "EmployeeAssignmentEndView",
    "EmployeeManagerAssignmentView",
    "MyProfileView",
    "EmployeeUserLinkView",
    "EmployeeUserUnlinkView",
    "EmployeeHistoryView",
]
