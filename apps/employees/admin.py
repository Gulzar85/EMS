from __future__ import annotations

from django.contrib import admin

from apps.employees.models import (
    EmergencyContact,
    Employee,
    EmployeeContact,
    EmployeeEmployment,
    EmployeeManagerAssignment,
    EmployeeNumberSequence,
    EmployeePositionAssignment,
)


class EmployeeContactInline(admin.StackedInline):
    model = EmployeeContact
    can_delete = False


class EmployeeEmploymentInline(admin.StackedInline):
    model = EmployeeEmployment
    can_delete = False


class EmergencyContactInline(admin.TabularInline):
    model = EmergencyContact
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_number",
        "display_name",
        "current_position",
        "current_manager",
        "employment_status",
    )
    list_filter = ("employment__status", "employment__employment_type", "gender")
    search_fields = ("employee_number", "first_name", "last_name", "preferred_name", "contact__work_email")
    autocomplete_fields = ("current_position", "current_manager", "user")
    readonly_fields = ("public_id", "employee_number", "created_at", "updated_at")
    inlines = [EmployeeContactInline, EmployeeEmploymentInline, EmergencyContactInline]

    @admin.display(description="Status")
    def employment_status(self, obj: Employee) -> str:
        employment = getattr(obj, "employment", None)
        return employment.get_status_display() if employment else "—"


@admin.register(EmployeePositionAssignment)
class EmployeePositionAssignmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "position", "assignment_type", "is_primary", "start_date", "end_date")
    list_filter = ("assignment_type", "is_primary")
    autocomplete_fields = ("employee", "position")
    search_fields = ("employee__employee_number", "employee__first_name", "employee__last_name")


@admin.register(EmployeeManagerAssignment)
class EmployeeManagerAssignmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "manager", "relationship_type", "is_primary", "start_date", "end_date")
    list_filter = ("relationship_type", "is_primary")
    autocomplete_fields = ("employee", "manager")
    search_fields = ("employee__employee_number", "employee__first_name", "employee__last_name")


@admin.register(EmployeeNumberSequence)
class EmployeeNumberSequenceAdmin(admin.ModelAdmin):
    list_display = ("last_value",)

    def has_add_permission(self, request) -> bool:
        return not EmployeeNumberSequence.objects.exists()
