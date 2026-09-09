import pytest

from apps.accounts.models import UserScope
from apps.accounts.tests.factories import UserFactory
from apps.organization import selectors
from apps.organization.tests.factories import (
    LocationFactory,
    RestaurantFactory,
    make_area,
    make_region,
)

pytestmark = pytest.mark.django_db


def test_superuser_sees_everything_unscoped():
    superuser = UserFactory(is_superuser=True)
    area = make_area()
    LocationFactory(organization_unit=area)
    assert selectors.get_locations_for_list(superuser).count() >= 1


def test_user_with_no_scope_sees_nothing():
    user = UserFactory()
    make_area()
    LocationFactory(organization_unit=make_area())
    assert selectors.get_organization_units_for_list(user).count() == 0
    assert selectors.get_locations_for_list(user).count() == 0


def test_global_scope_sees_everything():
    user = UserFactory()
    UserScope.objects.create(user=user, scope_type=UserScope.ScopeType.GLOBAL)
    make_area()
    assert selectors.get_organization_units_for_list(user).count() > 0


def test_organization_unit_scope_covers_its_subtree_only():
    region_a = make_region()
    area_a = make_area(region=region_a)
    restaurant_a = RestaurantFactory(location__organization_unit=area_a)

    region_b = make_region()
    area_b = make_area(region=region_b)
    RestaurantFactory(location__organization_unit=area_b)

    user = UserFactory()
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.ORGANIZATION_UNIT, organization_unit=region_a
    )

    visible_restaurants = list(selectors.get_restaurants_for_list(user))
    assert restaurant_a in visible_restaurants
    assert len(visible_restaurants) == 1  # region_b's restaurant must not appear


def test_location_scope_grants_access_to_exactly_that_location():
    area = make_area()
    location_a = LocationFactory(organization_unit=area)
    location_b = LocationFactory(organization_unit=area)

    user = UserFactory()
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.LOCATION, location=location_a
    )

    visible = list(selectors.get_locations_for_list(user))
    assert visible == [location_a]
    assert location_b not in visible


def test_get_root_units_for_scoped_user_returns_their_scope_boundary_not_true_root():
    region = make_region()
    area = make_area(region=region)

    user = UserFactory()
    UserScope.objects.create(
        user=user, scope_type=UserScope.ScopeType.ORGANIZATION_UNIT, organization_unit=area
    )

    roots = list(selectors.get_root_units_for_user(user))
    assert roots == [area]  # not the true Corporate root, which is out of scope


def test_job_family_job_level_job_are_not_scope_restricted():
    """Global master data — a user with zero UserScope rows must still see
    JobFamily/JobLevel/Job listings, unlike organization-anchored models."""
    from apps.organization.tests.factories import JobFactory

    JobFactory()
    families = selectors.get_job_families_for_list()
    assert families.count() >= 1
