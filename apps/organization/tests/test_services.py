import pytest

from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditLog
from apps.organization import services
from apps.organization.exceptions import OrganizationValidationError
from apps.organization.models import Location, OrganizationUnit, Position, Restaurant
from apps.organization.tests.factories import (
    CompanyFactory,
    DepartmentFactory,
    JobFactory,
    LocationFactory,
    OrganizationUnitFactory,
    PositionFactory,
    make_area,
)

pytestmark = pytest.mark.django_db


# --- OrganizationUnit ---------------------------------------------------


def test_create_organization_unit_happy_path():
    company = CompanyFactory()
    corporate = OrganizationUnitFactory(
        company=company, unit_type=OrganizationUnit.UnitType.CORPORATE
    )
    actor = UserFactory()

    unit = services.create_organization_unit(
        company=company,
        parent=corporate,
        name="Region East",
        code="REG-E",
        unit_type="region",
        actor=actor,
    )

    assert unit.pk is not None
    assert AuditLog.objects.filter(
        action="organization_unit.created", entity_id=str(unit.public_id)
    ).exists()


def test_create_organization_unit_rejects_invalid_parent_type():
    company = CompanyFactory()
    area = make_area()  # wrong parent type for a region
    with pytest.raises(Exception):  # noqa: B017 — full_clean() raises django ValidationError
        services.create_organization_unit(
            company=company,
            parent=area,
            name="Bad Region",
            code="BADR",
            unit_type="region",
            actor=None,
        )


# --- Restaurant (multi-model creation) -----------------------------------------


def test_create_restaurant_creates_location_and_restaurant_together():
    area = make_area()
    actor = UserFactory()

    restaurant = services.create_restaurant(
        organization_unit=area,
        code="LOC-TEST-001",
        name="Test Restaurant",
        restaurant_number="MCD-9001",
        actor=actor,
        city="Lahore",
    )

    assert Location.objects.filter(code="LOC-TEST-001").exists()
    assert restaurant.location.name == "Test Restaurant"
    assert restaurant.location.location_type == Location.LocationType.RESTAURANT
    assert restaurant.location.city == "Lahore"
    assert AuditLog.objects.filter(action="restaurant.created").exists()


def test_update_restaurant_status_change_is_audited_distinctly():
    restaurant = services.create_restaurant(
        organization_unit=make_area(),
        code="LOC-TEST-002",
        name="R2",
        restaurant_number="MCD-9002",
        actor=None,
    )
    services.update_restaurant(
        restaurant=restaurant, actor=None, operational_status=Restaurant.OperationalStatus.CLOSED
    )
    restaurant.refresh_from_db()
    assert restaurant.operational_status == Restaurant.OperationalStatus.CLOSED
    assert AuditLog.objects.filter(action="restaurant.status_changed").exists()


# --- Department -----------------------------------------------------------------


def test_create_department_happy_path():
    location = LocationFactory()
    department = services.create_department(
        organization_unit=None,
        location=location,
        parent=None,
        code="DEPT-X",
        name="Kitchen",
        actor=None,
    )
    assert department.location_id == location.id


# --- Position lifecycle -----------------------------------------------------------


def test_create_position_happy_path():
    department = DepartmentFactory()
    job = JobFactory()
    position = services.create_position(
        job=job,
        organization_unit=None,
        department=department,
        reports_to=None,
        code="POS-X",
        title="Test Position",
        actor=None,
    )
    assert position.status == Position.Status.DRAFT


def test_activate_position():
    position = PositionFactory(status=Position.Status.DRAFT)
    activated = services.activate_position(position=position, actor=None, reason="go live")
    assert activated.status == Position.Status.ACTIVE
    assert AuditLog.objects.filter(action="position.activated", reason="go live").exists()


def test_activate_already_active_position_rejected():
    position = PositionFactory(status=Position.Status.ACTIVE)
    with pytest.raises(OrganizationValidationError):
        services.activate_position(position=position, actor=None)


def test_freeze_requires_active_status():
    position = PositionFactory(status=Position.Status.DRAFT)
    with pytest.raises(OrganizationValidationError):
        services.freeze_position(position=position, actor=None)


def test_freeze_then_unfreeze_cycle():
    position = PositionFactory(status=Position.Status.ACTIVE)
    frozen = services.freeze_position(position=position, actor=None)
    assert frozen.status == Position.Status.FROZEN
    unfrozen = services.unfreeze_position(position=frozen, actor=None)
    assert unfrozen.status == Position.Status.ACTIVE


def test_unfreeze_requires_frozen_status():
    position = PositionFactory(status=Position.Status.ACTIVE)
    with pytest.raises(OrganizationValidationError):
        services.unfreeze_position(position=position, actor=None)


def test_deactivate_position_closes_it():
    position = PositionFactory(status=Position.Status.ACTIVE)
    closed = services.deactivate_position(position=position, actor=None)
    assert closed.status == Position.Status.CLOSED


def test_duplicate_position_creates_a_new_draft_not_active():
    """Duplicating must never copy an ACTIVE position as already-active —
    the copy always starts as a fresh DRAFT (Phase 03 plan's own testing
    guidance: "duplicate creates a DRAFT copy not an ACTIVE one")."""
    original = PositionFactory(status=Position.Status.ACTIVE, headcount_limit=5)

    duplicate = services.duplicate_position(
        position=original, new_code="POS-DUP-1", new_title="Duplicated Position", actor=None
    )

    assert duplicate.pk != original.pk
    assert duplicate.status == Position.Status.DRAFT
    assert duplicate.headcount_limit == 5
    assert duplicate.job_id == original.job_id
    assert AuditLog.objects.filter(action="position.duplicated").exists()


def test_duplicate_position_requires_unique_new_code():
    original = PositionFactory()
    with pytest.raises(Exception):  # noqa: B017 — IntegrityError/ValidationError from unique code
        services.duplicate_position(
            position=original, new_code=original.code, new_title="Dup", actor=None
        )
