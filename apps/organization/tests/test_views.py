import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.models import UserScope
from apps.accounts.tests.factories import UserFactory
from apps.organization.models import OrganizationUnit, Position
from apps.organization.tests.factories import (
    CompanyFactory,
    JobFactory,
    OrganizationUnitFactory,
    PositionFactory,
    RestaurantFactory,
    make_area,
    make_region,
)

pytestmark = pytest.mark.django_db


def _permissioned_user(*codenames):
    user = UserFactory()
    perms = Permission.objects.filter(
        content_type__app_label="organization", codename__in=codenames
    )
    user.user_permissions.add(*perms)
    UserScope.objects.create(user=user, scope_type=UserScope.ScopeType.GLOBAL)
    return user


# --- Dashboard ---------------------------------------------------------------


def test_dashboard_redirects_anonymous_to_login(client):
    response = client.get(reverse("organization:dashboard"))
    assert response.status_code == 302


def test_dashboard_forbidden_without_permission(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get(reverse("organization:dashboard"))
    assert response.status_code == 403


def test_dashboard_ok_with_permission(client):
    user = _permissioned_user("view_organizationunit")
    client.force_login(user)
    response = client.get(reverse("organization:dashboard"))
    assert response.status_code == 200
    assert "metrics" in response.context


# --- OrganizationUnit CRUD ----------------------------------------------------


def test_unit_create_via_post(client):
    user = _permissioned_user("add_organizationunit")
    client.force_login(user)
    company = CompanyFactory()
    corporate = OrganizationUnitFactory(
        company=company, unit_type=OrganizationUnit.UnitType.CORPORATE
    )

    response = client.post(
        reverse("organization:unit-create"),
        {
            "company": company.pk,
            "parent": corporate.pk,
            "name": "Region West",
            "code": "REG-W",
            "unit_type": "region",
            "description": "",
            "sort_order": 0,
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    assert OrganizationUnit.objects.filter(code="REG-W").exists()


def test_unit_delete_get_never_mutates(client):
    user = _permissioned_user("view_organizationunit", "delete_organizationunit")
    client.force_login(user)
    unit = OrganizationUnitFactory(unit_type=OrganizationUnit.UnitType.CORPORATE)

    response = client.get(reverse("organization:unit-delete", kwargs={"public_id": unit.public_id}))

    assert response.status_code == 200  # confirmation page only
    assert OrganizationUnit.objects.filter(pk=unit.pk).exists()


def test_unit_delete_refuses_when_protected(client):
    user = _permissioned_user("delete_organizationunit")
    client.force_login(user)
    region = make_region()

    response = client.post(
        reverse(
            "organization:unit-delete",
            kwargs={
                "public_id": region.company.organization_units.get(unit_type="corporate").public_id
            },
        )
    )

    assert response.status_code == 302  # redirected back to detail with an error message, not a 500
    assert OrganizationUnit.objects.filter(unit_type="corporate").exists()


def test_unit_list_htmx_returns_partial(client):
    user = _permissioned_user("view_organizationunit")
    client.force_login(user)
    OrganizationUnitFactory(unit_type=OrganizationUnit.UnitType.CORPORATE)

    response = client.get(reverse("organization:unit-list"), headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert b"<html" not in response.content.lower()


# --- Scoping enforced at the object level, not just the list -----------------


def test_scoped_out_user_gets_404_on_direct_detail_url(client):
    region_a = make_region()
    area_a = make_area(region=region_a)
    restaurant = RestaurantFactory(location__organization_unit=area_a)

    other_area = make_area()  # a different region/area entirely
    user = UserFactory()
    perms = Permission.objects.filter(
        content_type__app_label="organization", codename="view_restaurant"
    )
    user.user_permissions.add(*perms)
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.ORGANIZATION_UNIT, organization_unit=other_area
    )
    client.force_login(user)

    response = client.get(
        reverse("organization:restaurant-detail", kwargs={"public_id": restaurant.public_id})
    )

    assert response.status_code == 404  # object exists, but is outside this user's scope


def test_scoped_user_can_access_their_own_restaurant(client):
    area = make_area()
    restaurant = RestaurantFactory(location__organization_unit=area)

    user = UserFactory()
    perms = Permission.objects.filter(
        content_type__app_label="organization", codename="view_restaurant"
    )
    user.user_permissions.add(*perms)
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.ORGANIZATION_UNIT, organization_unit=area
    )
    client.force_login(user)

    response = client.get(
        reverse("organization:restaurant-detail", kwargs={"public_id": restaurant.public_id})
    )

    assert response.status_code == 200


# --- Restaurant (combined Location + Restaurant creation) --------------------


def test_restaurant_create_creates_location_and_restaurant(client):
    user = _permissioned_user("add_restaurant")
    client.force_login(user)
    area = make_area()

    response = client.post(
        reverse("organization:restaurant-create"),
        {
            "organization_unit": area.pk,
            "code": "LOC-NEW-01",
            "name": "New Restaurant",
            "restaurant_number": "MCD-8001",
            "restaurant_type": "standalone",
            "operational_status": "planned",
            "address": "",
            "city": "Karachi",
            "district": "",
            "province": "",
            "postal_code": "",
            "phone": "",
            "email": "",
        },
    )

    assert response.status_code == 302
    from apps.organization.models import Restaurant

    assert Restaurant.objects.filter(restaurant_number="MCD-8001").exists()


# --- Position workflows -------------------------------------------------------


def test_position_activate_via_post(client):
    user = _permissioned_user("view_position", "change_position")
    client.force_login(user)
    position = PositionFactory(status=Position.Status.DRAFT)

    response = client.post(
        reverse("organization:position-activate", kwargs={"public_id": position.public_id}),
        {"reason": "launch"},
    )

    assert response.status_code == 302
    position.refresh_from_db()
    assert position.status == Position.Status.ACTIVE


def test_position_activate_get_never_mutates(client):
    user = _permissioned_user("view_position", "change_position")
    client.force_login(user)
    position = PositionFactory(status=Position.Status.DRAFT)

    client.get(reverse("organization:position-activate", kwargs={"public_id": position.public_id}))

    position.refresh_from_db()
    assert position.status == Position.Status.DRAFT


def test_position_activate_twice_shows_error_not_crash(client):
    user = _permissioned_user("view_position", "change_position")
    client.force_login(user)
    position = PositionFactory(status=Position.Status.ACTIVE)

    response = client.post(
        reverse("organization:position-activate", kwargs={"public_id": position.public_id}),
        {"reason": ""},
    )

    assert response.status_code == 302  # redirected back with an error message, not a 500


def test_position_duplicate_creates_new_draft_position(client):
    user = _permissioned_user("view_position", "add_position")
    client.force_login(user)
    position = PositionFactory(status=Position.Status.ACTIVE)

    response = client.post(
        reverse("organization:position-duplicate", kwargs={"public_id": position.public_id}),
        {"new_code": "POS-DUP-VIEW", "new_title": "Duplicated"},
    )

    assert response.status_code == 302
    duplicate = Position.objects.get(code="POS-DUP-VIEW")
    assert duplicate.status == Position.Status.DRAFT


def test_position_workflow_requires_change_permission(client):
    user = _permissioned_user("view_position")  # no change_position
    client.force_login(user)
    position = PositionFactory(status=Position.Status.DRAFT)

    response = client.post(
        reverse("organization:position-activate", kwargs={"public_id": position.public_id}),
        {"reason": ""},
    )

    assert response.status_code == 403


# --- Job (global master data, always visible regardless of scope) ------------


def test_job_list_visible_without_any_organization_scope(client):
    user = UserFactory()
    perms = Permission.objects.filter(content_type__app_label="organization", codename="view_job")
    user.user_permissions.add(*perms)
    client.force_login(user)
    JobFactory()

    response = client.get(reverse("organization:job-list"))

    assert response.status_code == 200
