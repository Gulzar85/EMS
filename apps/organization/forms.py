"""Organization forms — the authoritative validation boundary. ModelForms
rely on Django's own `instance.full_clean()` call (triggered automatically
by ModelForm._post_clean()) to surface each model's clean() hierarchy/
cycle validation as ordinary form errors — no duplicated validation logic.
"""

from __future__ import annotations

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout
from django import forms

from apps.organization.models import (
    Department,
    Job,
    JobFamily,
    JobLevel,
    Location,
    OrganizationUnit,
    Position,
    Restaurant,
)


class OrganizationUnitForm(forms.ModelForm):
    class Meta:
        model = OrganizationUnit
        fields = [
            "company",
            "parent",
            "name",
            "code",
            "unit_type",
            "description",
            "sort_order",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = [
            "organization_unit",
            "code",
            "name",
            "location_type",
            "address",
            "city",
            "district",
            "province",
            "postal_code",
            "latitude",
            "longitude",
            "phone",
            "email",
            "opened_on",
            "closed_on",
            "is_active",
        ]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}


class RestaurantForm(forms.Form):
    """Spans two models (Location + Restaurant) — not a ModelForm. The
    view splits `cleaned_data` back out and calls
    services.create_restaurant()/update_restaurant() (Phase 03 plan
    judgment call #11).
    """

    organization_unit = forms.ModelChoiceField(
        queryset=OrganizationUnit.objects.filter(is_active=True)
    )
    code = forms.CharField(max_length=20, label="Location code")
    name = forms.CharField(max_length=150, label="Restaurant name")
    restaurant_number = forms.CharField(max_length=20)
    restaurant_type = forms.ChoiceField(choices=Restaurant.RestaurantType.choices)
    operational_status = forms.ChoiceField(choices=Restaurant.OperationalStatus.choices)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    city = forms.CharField(max_length=100, required=False)
    district = forms.CharField(max_length=100, required=False)
    province = forms.CharField(max_length=100, required=False)
    postal_code = forms.CharField(max_length=20, required=False)
    phone = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=False)
    opening_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    closing_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Restaurant",
                "organization_unit",
                "code",
                "name",
                "restaurant_number",
                "restaurant_type",
                "operational_status",
            ),
            Fieldset(
                "Address",
                "address",
                "city",
                "district",
                "province",
                "postal_code",
                "phone",
                "email",
            ),
            Fieldset("Dates", "opening_date", "closing_date"),
        )

    def clean(self):
        cleaned = super().clean()
        opening, closing = cleaned.get("opening_date"), cleaned.get("closing_date")
        if opening and closing and closing < opening:
            self.add_error("closing_date", "Closing date cannot be before the opening date.")
        return cleaned

    @classmethod
    def from_restaurant(cls, restaurant: Restaurant, **kwargs) -> RestaurantForm:
        location = restaurant.location
        initial = {
            "organization_unit": location.organization_unit_id,
            "code": location.code,
            "name": location.name,
            "restaurant_number": restaurant.restaurant_number,
            "restaurant_type": restaurant.restaurant_type,
            "operational_status": restaurant.operational_status,
            "address": location.address,
            "city": location.city,
            "district": location.district,
            "province": location.province,
            "postal_code": location.postal_code,
            "phone": location.phone,
            "email": location.email,
            "opening_date": restaurant.opening_date,
            "closing_date": restaurant.closing_date,
        }
        return cls(initial=initial, **kwargs)


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = [
            "organization_unit",
            "location",
            "parent",
            "code",
            "name",
            "description",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class JobFamilyForm(forms.ModelForm):
    class Meta:
        model = JobFamily
        fields = ["code", "name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class JobLevelForm(forms.ModelForm):
    class Meta:
        model = JobLevel
        fields = ["code", "name", "rank", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "code",
            "title",
            "description",
            "job_family",
            "job_level",
            "employment_category",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = [
            "job",
            "organization_unit",
            "department",
            "reports_to",
            "code",
            "title",
            "position_type",
            "headcount_limit",
            "effective_from",
            "effective_to",
        ]
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["reports_to"].queryset = Position.objects.exclude(pk=self.instance.pk)


class PositionActionForm(forms.Form):
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class PositionDuplicateForm(forms.Form):
    new_code = forms.CharField(max_length=30, label="New position code")
    new_title = forms.CharField(max_length=150, label="New position title")
