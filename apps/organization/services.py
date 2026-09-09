"""Organization business operations.

Services exist here for genuinely meaningful domain logic (multi-model
writes, hierarchy validation, lifecycle transitions, audit) — not as a
ceremonial wrapper around `.save()` (Phase 03 plan §44). Straightforward
single-model edits with no extra rule (e.g. JobFamily/JobLevel) are left
to plain ModelForm + CBV `form_valid()`, matching the same bar Phase 02
used for Theme.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.audit.services import record as record_audit
from apps.organization.exceptions import OrganizationValidationError
from apps.organization.models import Department, Location, OrganizationUnit, Position, Restaurant
from apps.organization.permissions import invalidate_unit_tree_cache


@transaction.atomic
def create_organization_unit(
    *,
    company,
    parent,
    name: str,
    code: str,
    unit_type: str,
    description: str = "",
    actor: User | None,
) -> OrganizationUnit:
    unit = OrganizationUnit(
        company=company,
        parent=parent,
        name=name,
        code=code,
        unit_type=unit_type,
        description=description,
    )
    unit.full_clean()
    unit.save()
    invalidate_unit_tree_cache()
    record_audit(
        actor=actor,
        action="organization_unit.created",
        entity=unit,
        after={"name": name, "code": code},
    )
    return unit


@transaction.atomic
def update_organization_unit(
    *, unit: OrganizationUnit, actor: User | None, **fields
) -> OrganizationUnit:
    before = {"name": unit.name, "parent_id": unit.parent_id, "is_active": unit.is_active}
    for field, value in fields.items():
        setattr(unit, field, value)
    unit.full_clean()
    unit.save()
    invalidate_unit_tree_cache()
    record_audit(
        actor=actor,
        action="organization_unit.updated",
        entity=unit,
        before=before,
        after={"name": unit.name, "parent_id": unit.parent_id, "is_active": unit.is_active},
    )
    return unit


@transaction.atomic
def create_restaurant(
    *,
    organization_unit: OrganizationUnit,
    code: str,
    name: str,
    restaurant_number: str,
    actor: User | None,
    **location_and_restaurant_fields,
) -> Restaurant:
    """A restaurant is a Location row + a Restaurant profile row, created
    together — exactly the "meaningful domain logic" bar for a service
    rather than a plain form.save() (Phase 03 plan §44, judgment call #11).
    """
    location_fields = {
        k: v
        for k, v in location_and_restaurant_fields.items()
        if k
        in {
            "address",
            "city",
            "district",
            "province",
            "postal_code",
            "latitude",
            "longitude",
            "phone",
            "email",
            "is_active",
            "opened_on",
            "closed_on",
        }
    }
    restaurant_fields = {
        k: v
        for k, v in location_and_restaurant_fields.items()
        if k in {"restaurant_type", "operational_status", "opening_date", "closing_date"}
    }

    location = Location(
        organization_unit=organization_unit,
        code=code,
        name=name,
        location_type=Location.LocationType.RESTAURANT,
        **location_fields,
    )
    location.full_clean()
    location.save()

    restaurant = Restaurant(
        location=location, restaurant_number=restaurant_number, **restaurant_fields
    )
    restaurant.full_clean()
    restaurant.save()

    record_audit(
        actor=actor,
        action="restaurant.created",
        entity=restaurant,
        after={"restaurant_number": restaurant_number, "name": name},
    )
    return restaurant


@transaction.atomic
def update_restaurant(*, restaurant: Restaurant, actor: User | None, **fields) -> Restaurant:
    location_field_names = {
        "code",
        "name",
        "address",
        "city",
        "district",
        "province",
        "postal_code",
        "latitude",
        "longitude",
        "phone",
        "email",
        "is_active",
        "opened_on",
        "closed_on",
    }
    before = {
        "operational_status": restaurant.operational_status,
        "name": restaurant.location.name,
    }
    location_changed = False
    for field, value in fields.items():
        if field in location_field_names:
            setattr(restaurant.location, field, value)
            location_changed = True
        else:
            setattr(restaurant, field, value)

    if location_changed:
        restaurant.location.full_clean()
        restaurant.location.save()
    restaurant.full_clean()
    restaurant.save()

    after = {"operational_status": restaurant.operational_status, "name": restaurant.location.name}
    action = (
        "restaurant.status_changed"
        if before["operational_status"] != after["operational_status"]
        else "restaurant.updated"
    )
    record_audit(actor=actor, action=action, entity=restaurant, before=before, after=after)
    return restaurant


@transaction.atomic
def create_department(
    *,
    organization_unit: OrganizationUnit | None,
    location: Location | None,
    parent: Department | None,
    code: str,
    name: str,
    description: str = "",
    actor: User | None,
) -> Department:
    department = Department(
        organization_unit=organization_unit,
        location=location,
        parent=parent,
        code=code,
        name=name,
        description=description,
    )
    department.full_clean()
    department.save()
    record_audit(
        actor=actor,
        action="department.created",
        entity=department,
        after={"name": name, "code": code},
    )
    return department


@transaction.atomic
def update_department(*, department: Department, actor: User | None, **fields) -> Department:
    before = {"name": department.name, "is_active": department.is_active}
    for field, value in fields.items():
        setattr(department, field, value)
    department.full_clean()
    department.save()
    record_audit(
        actor=actor,
        action="department.updated",
        entity=department,
        before=before,
        after={"name": department.name, "is_active": department.is_active},
    )
    return department


@transaction.atomic
def create_position(
    *,
    job,
    organization_unit: OrganizationUnit | None,
    department: Department | None,
    reports_to: Position | None,
    code: str,
    title: str,
    actor: User | None,
    **fields,
) -> Position:
    position = Position(
        job=job,
        organization_unit=organization_unit,
        department=department,
        reports_to=reports_to,
        code=code,
        title=title,
        **fields,
    )
    position.full_clean()
    position.save()
    record_audit(
        actor=actor,
        action="position.created",
        entity=position,
        after={"code": code, "title": title},
    )
    return position


@transaction.atomic
def update_position(*, position: Position, actor: User | None, **fields) -> Position:
    before = {
        "title": position.title,
        "status": position.status,
        "department_id": position.department_id,
    }
    for field, value in fields.items():
        setattr(position, field, value)
    position.full_clean()
    position.save()
    record_audit(
        actor=actor,
        action="position.updated",
        entity=position,
        before=before,
        after={
            "title": position.title,
            "status": position.status,
            "department_id": position.department_id,
        },
    )
    return position


def _transition_position(
    position: Position, *, new_status: str, action: str, actor: User | None, reason: str = ""
) -> Position:
    before_status = position.status
    position.status = new_status
    position.full_clean()
    position.save(update_fields=["status", "updated_at"])
    record_audit(
        actor=actor,
        action=action,
        entity=position,
        before={"status": before_status},
        after={"status": new_status},
        reason=reason,
    )
    return position


@transaction.atomic
def activate_position(*, position: Position, actor: User | None, reason: str = "") -> Position:
    if position.status == Position.Status.ACTIVE:
        raise OrganizationValidationError("This position is already active.")
    return _transition_position(
        position,
        new_status=Position.Status.ACTIVE,
        action="position.activated",
        actor=actor,
        reason=reason,
    )


@transaction.atomic
def deactivate_position(*, position: Position, actor: User | None, reason: str = "") -> Position:
    return _transition_position(
        position,
        new_status=Position.Status.CLOSED,
        action="position.deactivated",
        actor=actor,
        reason=reason,
    )


@transaction.atomic
def freeze_position(*, position: Position, actor: User | None, reason: str = "") -> Position:
    if position.status != Position.Status.ACTIVE:
        raise OrganizationValidationError("Only an active position can be frozen.")
    return _transition_position(
        position,
        new_status=Position.Status.FROZEN,
        action="position.frozen",
        actor=actor,
        reason=reason,
    )


@transaction.atomic
def unfreeze_position(*, position: Position, actor: User | None, reason: str = "") -> Position:
    if position.status != Position.Status.FROZEN:
        raise OrganizationValidationError("Only a frozen position can be unfrozen.")
    return _transition_position(
        position,
        new_status=Position.Status.ACTIVE,
        action="position.unfrozen",
        actor=actor,
        reason=reason,
    )


@transaction.atomic
def duplicate_position(
    *, position: Position, new_code: str, new_title: str, actor: User | None
) -> Position:
    duplicate = Position(
        job=position.job,
        organization_unit=position.organization_unit,
        department=position.department,
        reports_to=position.reports_to,
        code=new_code,
        title=new_title,
        position_type=position.position_type,
        headcount_limit=position.headcount_limit,
        status=Position.Status.DRAFT,
    )
    duplicate.full_clean()
    duplicate.save()
    record_audit(
        actor=actor,
        action="position.duplicated",
        entity=duplicate,
        after={"source_position": str(position.public_id), "code": new_code},
    )
    return duplicate
