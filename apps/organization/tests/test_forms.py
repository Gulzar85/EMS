import pytest

from apps.organization.forms import PositionForm, RestaurantForm
from apps.organization.tests.factories import (
    DepartmentFactory,
    JobFactory,
    PositionFactory,
    make_area,
)

pytestmark = pytest.mark.django_db


def test_restaurant_form_valid_data():
    area = make_area()
    data = {
        "organization_unit": area.pk,
        "code": "LOC-F-1",
        "name": "Form Restaurant",
        "restaurant_number": "MCD-7001",
        "restaurant_type": "standalone",
        "operational_status": "operating",
        "address": "",
        "city": "Lahore",
        "district": "",
        "province": "",
        "postal_code": "",
        "phone": "",
        "email": "",
    }
    form = RestaurantForm(data)
    assert form.is_valid(), form.errors


def test_restaurant_form_rejects_closing_before_opening():
    area = make_area()
    data = {
        "organization_unit": area.pk,
        "code": "LOC-F-2",
        "name": "Form Restaurant 2",
        "restaurant_number": "MCD-7002",
        "restaurant_type": "standalone",
        "operational_status": "operating",
        "opening_date": "2026-06-01",
        "closing_date": "2026-01-01",
    }
    form = RestaurantForm(data)
    assert not form.is_valid()
    assert "closing_date" in form.errors


def test_position_form_excludes_self_from_reports_to_choices_on_update():
    position = PositionFactory()
    form = PositionForm(instance=position)
    assert position not in form.fields["reports_to"].queryset


def test_position_form_valid_data():
    department = DepartmentFactory()
    job = JobFactory()
    data = {
        "job": job.pk,
        "department": department.pk,
        "code": "POS-FORM-1",
        "title": "Form Position",
        "position_type": "individual_contributor",
        "headcount_limit": 3,
    }
    form = PositionForm(data)
    assert form.is_valid(), form.errors
