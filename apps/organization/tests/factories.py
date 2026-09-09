import factory
from factory.django import DjangoModelFactory

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


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Sequence(lambda n: f"Test Company {n}")
    code = factory.Sequence(lambda n: f"CO{n}")
    slug = factory.Sequence(lambda n: f"test-company-{n}")


class OrganizationUnitFactory(DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    company = factory.SubFactory(CompanyFactory)
    name = factory.Sequence(lambda n: f"Unit {n}")
    code = factory.Sequence(lambda n: f"UNIT{n}")
    unit_type = OrganizationUnit.UnitType.CORPORATE
    parent = None


def make_region(**kwargs):
    company = kwargs.pop("company", None) or CompanyFactory()
    corporate = OrganizationUnitFactory(
        company=company, unit_type=OrganizationUnit.UnitType.CORPORATE, parent=None
    )
    return OrganizationUnitFactory(
        company=company, unit_type=OrganizationUnit.UnitType.REGION, parent=corporate, **kwargs
    )


def make_area(**kwargs):
    region = kwargs.pop("region", None) or make_region()
    return OrganizationUnitFactory(
        company=region.company, unit_type=OrganizationUnit.UnitType.AREA, parent=region, **kwargs
    )


class LocationFactory(DjangoModelFactory):
    class Meta:
        model = Location

    organization_unit = factory.LazyFunction(make_area)
    code = factory.Sequence(lambda n: f"LOC{n}")
    name = factory.Sequence(lambda n: f"Location {n}")
    location_type = Location.LocationType.RESTAURANT


class RestaurantFactory(DjangoModelFactory):
    class Meta:
        model = Restaurant

    location = factory.SubFactory(LocationFactory)
    restaurant_number = factory.Sequence(lambda n: f"MCD-{n:04d}")


class DepartmentFactory(DjangoModelFactory):
    class Meta:
        model = Department

    location = factory.SubFactory(LocationFactory)
    code = factory.Sequence(lambda n: f"DEPT{n}")
    name = factory.Sequence(lambda n: f"Department {n}")


class JobFamilyFactory(DjangoModelFactory):
    class Meta:
        model = JobFamily

    code = factory.Sequence(lambda n: f"FAM{n}")
    name = factory.Sequence(lambda n: f"Family {n}")


class JobLevelFactory(DjangoModelFactory):
    class Meta:
        model = JobLevel

    code = factory.Sequence(lambda n: f"LVL{n}")
    name = factory.Sequence(lambda n: f"Level {n}")
    rank = factory.Sequence(lambda n: n + 1)


class JobFactory(DjangoModelFactory):
    class Meta:
        model = Job

    code = factory.Sequence(lambda n: f"JOB{n}")
    title = factory.Sequence(lambda n: f"Job {n}")
    job_family = factory.SubFactory(JobFamilyFactory)
    job_level = factory.SubFactory(JobLevelFactory)
    employment_category = Job.EmploymentCategory.FULL_TIME


class PositionFactory(DjangoModelFactory):
    class Meta:
        model = Position

    job = factory.SubFactory(JobFactory)
    department = factory.SubFactory(DepartmentFactory)
    code = factory.Sequence(lambda n: f"POS{n}")
    title = factory.Sequence(lambda n: f"Position {n}")
    status = Position.Status.DRAFT
    headcount_limit = 1
