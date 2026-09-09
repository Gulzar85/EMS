from django.contrib import admin

from apps.organization.models import (
    Company,
    Department,
    Job,
    JobFamily,
    JobLevel,
    Location,
    OrganizationUnit,
    Position,
    Restaurant,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    search_fields = ["name", "code"]


@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "unit_type", "parent", "is_active"]
    list_filter = ["unit_type", "is_active", "company"]
    search_fields = ["name", "code"]
    autocomplete_fields = ["parent", "company"]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "location_type", "city", "is_active"]
    list_filter = ["location_type", "is_active", "province"]
    search_fields = ["code", "name", "city"]
    autocomplete_fields = ["organization_unit"]


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ["restaurant_number", "location", "restaurant_type", "operational_status"]
    list_filter = ["restaurant_type", "operational_status"]
    search_fields = ["restaurant_number", "location__name"]
    autocomplete_fields = ["location"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "organization_unit", "location", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    autocomplete_fields = ["organization_unit", "location", "parent"]


@admin.register(JobFamily)
class JobFamilyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    search_fields = ["name", "code"]


@admin.register(JobLevel)
class JobLevelAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "rank", "is_active"]
    search_fields = ["name", "code"]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["title", "code", "job_family", "job_level", "employment_category", "is_active"]
    list_filter = ["job_family", "job_level", "employment_category", "is_active"]
    search_fields = ["title", "code"]
    autocomplete_fields = ["job_family", "job_level"]


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "job", "department", "status", "headcount_limit"]
    list_filter = ["status", "position_type"]
    search_fields = ["code", "title"]
    autocomplete_fields = ["job", "organization_unit", "department", "reports_to"]
