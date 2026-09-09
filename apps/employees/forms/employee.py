"""Employee forms deliberately split by concern (Phase 04 brief §35, §92):
`EmployeeCreateForm` also captures the mandatory initial employment facts
(joining date, employment type); `EmployeeProfileForm` — used for Update —
never touches employment/lifecycle fields, since those change only through
`EmployeeLifecycleService` transitions, not a generic edit form.

Both span two models (Employee + EmployeeContact), following the same
"plain Form, split back out in the service" pattern
`apps.organization.forms.RestaurantForm` established in Phase 03 for
Location+Restaurant.
"""

from __future__ import annotations

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout
from django import forms

from apps.employees.models import Employee
from apps.employees.validators import validate_profile_photo
from apps.organization.models import Job

_GENDER_CHOICES = [("", "—")] + list(Employee.Gender.choices)
_MARITAL_STATUS_CHOICES = [("", "—")] + list(Employee.MaritalStatus.choices)


class _EmployeeIdentityFields(forms.Form):
    first_name = forms.CharField(max_length=100)
    middle_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100)
    preferred_name = forms.CharField(max_length=100, required=False)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    gender = forms.ChoiceField(choices=_GENDER_CHOICES, required=False)
    nationality = forms.CharField(max_length=100, required=False)
    marital_status = forms.ChoiceField(choices=_MARITAL_STATUS_CHOICES, required=False)
    profile_photo = forms.ImageField(required=False)

    personal_email = forms.EmailField(required=False)
    work_email = forms.EmailField(required=False)
    mobile_number = forms.CharField(max_length=30, required=False)
    phone_number = forms.CharField(max_length=30, required=False)
    address_line_1 = forms.CharField(max_length=255, required=False)
    address_line_2 = forms.CharField(max_length=255, required=False)
    city = forms.CharField(max_length=100, required=False)
    district = forms.CharField(max_length=100, required=False)
    province = forms.CharField(max_length=100, required=False)
    postal_code = forms.CharField(max_length=20, required=False)
    country = forms.CharField(max_length=100, required=False)

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if photo:
            validate_profile_photo(photo)
        return photo


class EmployeeCreateForm(_EmployeeIdentityFields):
    joining_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    employment_type = forms.ChoiceField(choices=Job.EmploymentCategory.choices)
    probation_end_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Personal information",
                "first_name",
                "middle_name",
                "last_name",
                "preferred_name",
                "date_of_birth",
                "gender",
                "nationality",
                "marital_status",
                "profile_photo",
            ),
            Fieldset(
                "Contact information",
                "personal_email",
                "work_email",
                "mobile_number",
                "phone_number",
                "address_line_1",
                "address_line_2",
                "city",
                "district",
                "province",
                "postal_code",
                "country",
            ),
            Fieldset(
                "Employment",
                "joining_date",
                "employment_type",
                "probation_end_date",
            ),
        )


class EmployeeProfileForm(_EmployeeIdentityFields):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Personal information",
                "first_name",
                "middle_name",
                "last_name",
                "preferred_name",
                "date_of_birth",
                "gender",
                "nationality",
                "marital_status",
                "profile_photo",
            ),
            Fieldset(
                "Contact information",
                "personal_email",
                "work_email",
                "mobile_number",
                "phone_number",
                "address_line_1",
                "address_line_2",
                "city",
                "district",
                "province",
                "postal_code",
                "country",
            ),
        )

    @classmethod
    def from_employee(cls, employee: Employee, **kwargs) -> EmployeeProfileForm:
        contact = employee.contact
        initial = {
            "first_name": employee.first_name,
            "middle_name": employee.middle_name,
            "last_name": employee.last_name,
            "preferred_name": employee.preferred_name,
            "date_of_birth": employee.date_of_birth,
            "gender": employee.gender,
            "nationality": employee.nationality,
            "marital_status": employee.marital_status,
            "personal_email": contact.personal_email,
            "work_email": contact.work_email,
            "mobile_number": contact.mobile_number,
            "phone_number": contact.phone_number,
            "address_line_1": contact.address_line_1,
            "address_line_2": contact.address_line_2,
            "city": contact.city,
            "district": contact.district,
            "province": contact.province,
            "postal_code": contact.postal_code,
            "country": contact.country,
        }
        return cls(initial=initial, **kwargs)
