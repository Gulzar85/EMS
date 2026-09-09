import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.organization.models import Department, OrganizationUnit, Position
from apps.organization.tests.factories import (
    CompanyFactory,
    DepartmentFactory,
    JobFactory,
    LocationFactory,
    OrganizationUnitFactory,
    PositionFactory,
    RestaurantFactory,
    make_area,
    make_region,
)

pytestmark = pytest.mark.django_db


# --- OrganizationUnit hierarchy ---------------------------------------------


def test_corporate_unit_cannot_have_a_parent():
    company = CompanyFactory()
    corporate = OrganizationUnitFactory(
        company=company, unit_type=OrganizationUnit.UnitType.CORPORATE
    )
    other = OrganizationUnit(
        company=company,
        parent=corporate,
        name="Bad Corporate",
        code="BAD",
        unit_type=OrganizationUnit.UnitType.CORPORATE,
    )
    with pytest.raises(ValidationError):
        other.full_clean()


def test_region_requires_corporate_parent():
    company = CompanyFactory()
    area = make_area()  # an AREA, wrong parent type for a REGION
    region = OrganizationUnit(
        company=company,
        parent=area,
        name="Bad Region",
        code="BADREG",
        unit_type=OrganizationUnit.UnitType.REGION,
    )
    with pytest.raises(ValidationError):
        region.full_clean()


def test_valid_hierarchy_passes_clean():
    region = make_region()
    area = OrganizationUnit(
        company=region.company,
        parent=region,
        name="Valid Area",
        code="VALIDAREA",
        unit_type=OrganizationUnit.UnitType.AREA,
    )
    area.full_clean()  # must not raise


def test_organization_unit_cannot_be_its_own_parent():
    unit = OrganizationUnitFactory(unit_type=OrganizationUnit.UnitType.CORPORATE)
    unit.parent = unit
    unit.unit_type = OrganizationUnit.UnitType.REGION
    with pytest.raises(ValidationError):
        unit.full_clean()


def test_organization_unit_circular_parent_rejected():
    region = make_region()
    area = make_area(region=region)
    # Attempt to make the region a child of its own descendant area.
    region.parent = area
    with pytest.raises(ValidationError):
        region.full_clean()


def test_unique_code_per_company():
    company = CompanyFactory()
    OrganizationUnitFactory(
        company=company, code="DUP", unit_type=OrganizationUnit.UnitType.CORPORATE
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrganizationUnitFactory(
                company=company, code="DUP", unit_type=OrganizationUnit.UnitType.CORPORATE
            )


def test_same_code_allowed_across_different_companies():
    OrganizationUnitFactory(code="SHARED", unit_type=OrganizationUnit.UnitType.CORPORATE)
    OrganizationUnitFactory(
        code="SHARED", unit_type=OrganizationUnit.UnitType.CORPORATE
    )  # different company


# --- Location / Restaurant ---------------------------------------------------


def test_location_closed_on_before_opened_on_rejected():
    location = LocationFactory.build(opened_on="2026-01-10", closed_on="2026-01-01")
    with pytest.raises(ValidationError):
        location.full_clean()


def test_restaurant_closing_date_before_opening_date_rejected():
    restaurant = RestaurantFactory.build(opening_date="2026-01-10", closing_date="2026-01-01")
    with pytest.raises(ValidationError):
        restaurant.full_clean()


def test_restaurant_requires_unique_number():
    RestaurantFactory(restaurant_number="MCD-0001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RestaurantFactory(restaurant_number="MCD-0001")


# --- Department dual anchor ---------------------------------------------------


def test_department_requires_exactly_one_anchor():
    location = LocationFactory()
    department = Department(
        code="D1",
        name="Both anchors",
        organization_unit=location.organization_unit,
        location=location,
    )
    with pytest.raises(ValidationError):
        department.full_clean()


def test_department_with_no_anchor_rejected():
    department = Department(code="D2", name="No anchor")
    with pytest.raises(ValidationError):
        department.full_clean()


def test_department_with_location_anchor_is_valid():
    location = LocationFactory()
    department = Department(code="D3", name="Kitchen", location=location)
    department.full_clean()  # must not raise


def test_department_database_constraint_enforced_even_bypassing_clean():
    """The CheckConstraint is a second, DB-level line of defense — prove it
    fires even if application code skipped full_clean()."""
    location = LocationFactory()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Department.objects.create(
                code="D4",
                name="Bypass",
                organization_unit=location.organization_unit,
                location=location,
            )


def test_department_circular_parent_rejected():
    location = LocationFactory()
    parent_dept = DepartmentFactory(location=location)
    child_dept = DepartmentFactory(location=location, parent=parent_dept)
    parent_dept.parent = child_dept
    with pytest.raises(ValidationError):
        parent_dept.full_clean()


# --- Position ------------------------------------------------------------------


def test_position_requires_department_or_organization_unit():
    job = JobFactory()
    position = Position(job=job, code="P1", title="Orphan Position")
    with pytest.raises(ValidationError):
        position.full_clean()


def test_position_with_department_is_valid():
    # Not .build(): Position.job/department are required FKs, and an
    # unsaved (.build()) related object has no pk yet, which full_clean()
    # correctly rejects as "cannot be null" — a factory_boy/Django FK
    # interaction, not a real validation failure. Use the saved factory.
    position = PositionFactory()
    position.full_clean()  # must not raise


def test_position_cannot_report_to_itself():
    position = PositionFactory()
    position.reports_to = position
    with pytest.raises(ValidationError):
        position.full_clean()


def test_position_reports_to_cycle_rejected():
    manager = PositionFactory()
    report = PositionFactory(reports_to=manager)
    manager.reports_to = report
    with pytest.raises(ValidationError):
        manager.full_clean()


def test_position_headcount_calculations_when_fully_vacant():
    position = PositionFactory(headcount_limit=10, status=Position.Status.ACTIVE)
    assert position.occupied_headcount == 0
    assert position.vacant_headcount == 10
    assert position.vacancy_rate == 100.0
    assert position.utilization_rate == 0.0


def test_position_effective_to_before_from_rejected():
    position = PositionFactory.build(effective_from="2026-06-01", effective_to="2026-01-01")
    with pytest.raises(ValidationError):
        position.full_clean()
