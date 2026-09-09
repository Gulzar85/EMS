"""Idempotent development/demo seed data — safe to run repeatedly
(get_or_create throughout, per Phase 03 plan §84). No real employee data;
nothing employee-shaped exists yet to seed.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

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
from apps.organization.models.company import Company

REGIONS = {
    "Region North": ["Area Lahore", "Area Islamabad"],
    "Region South": ["Area Karachi"],
}

RESTAURANTS_BY_AREA = {
    "Area Lahore": ["Gulberg", "DHA Phase 5", "Mall Road", "Model Town"],
    "Area Islamabad": ["Blue Area", "F-10 Markaz"],
    "Area Karachi": ["Clifton", "Tariq Road", "PECHS", "North Nazimabad"],
}

BUSINESS_UNITS = ["Human Resources", "Finance", "Information Technology"]

JOB_FAMILIES = ["Restaurant Operations", "Corporate Support"]
JOB_LEVELS = [
    ("L1", "Entry", 1),
    ("L2", "Associate", 2),
    ("L3", "Supervisor", 3),
    ("L4", "Manager", 4),
]

JOBS = [
    # code, title, family, level, category, headcount_limit per restaurant
    ("CREW", "Crew Member", "Restaurant Operations", "L1", Job.EmploymentCategory.PART_TIME, 15),
    (
        "SHIFT-LEAD",
        "Shift Leader",
        "Restaurant Operations",
        "L2",
        Job.EmploymentCategory.FULL_TIME,
        4,
    ),
    (
        "ASST-MGR",
        "Assistant Manager",
        "Restaurant Operations",
        "L3",
        Job.EmploymentCategory.FULL_TIME,
        2,
    ),
    (
        "REST-MGR",
        "Restaurant Manager",
        "Restaurant Operations",
        "L4",
        Job.EmploymentCategory.FULL_TIME,
        1,
    ),
    ("HR-OFFICER", "HR Officer", "Corporate Support", "L2", Job.EmploymentCategory.FULL_TIME, 2),
]

DEPARTMENTS_PER_RESTAURANT = ["Kitchen", "Front Counter", "Drive-Thru"]


class Command(BaseCommand):
    help = "Seed realistic sample organization data (no real employee data)."

    @transaction.atomic
    def handle(self, *args, **options):
        company, _ = Company.objects.get_or_create(
            code="MCD-PK",
            defaults={
                "name": "McDonald's Pakistan",
                "legal_name": "McDonald's Pakistan (Pvt.) Ltd.",
                "slug": "mcdonalds-pakistan",
                "description": "Seed development data — not real corporate records.",
            },
        )

        corporate, _ = OrganizationUnit.objects.get_or_create(
            company=company,
            code="CORP",
            defaults={"name": "Corporate", "unit_type": OrganizationUnit.UnitType.CORPORATE},
        )

        for bu_name in BUSINESS_UNITS:
            OrganizationUnit.objects.get_or_create(
                company=company,
                code=f"BU-{bu_name[:3].upper()}",
                defaults={
                    "name": bu_name,
                    "unit_type": OrganizationUnit.UnitType.BUSINESS_UNIT,
                    "parent": corporate,
                },
            )

        area_units: dict[str, OrganizationUnit] = {}
        for region_name, areas in REGIONS.items():
            region, _ = OrganizationUnit.objects.get_or_create(
                company=company,
                code=f"REG-{region_name.split()[-1][:3].upper()}",
                defaults={
                    "name": region_name,
                    "unit_type": OrganizationUnit.UnitType.REGION,
                    "parent": corporate,
                },
            )
            for area_name in areas:
                area, _ = OrganizationUnit.objects.get_or_create(
                    company=company,
                    code=f"AREA-{area_name.split()[-1][:3].upper()}",
                    defaults={
                        "name": area_name,
                        "unit_type": OrganizationUnit.UnitType.AREA,
                        "parent": region,
                    },
                )
                area_units[area_name] = area

        job_families = {}
        for name in JOB_FAMILIES:
            job_families[name], _ = JobFamily.objects.get_or_create(
                code=name[:3].upper(), defaults={"name": name}
            )

        job_levels = {}
        for code, name, rank in JOB_LEVELS:
            job_levels[code], _ = JobLevel.objects.get_or_create(
                code=code, defaults={"name": name, "rank": rank}
            )

        jobs = {}
        for code, title, family, level, category, _headcount in JOBS:
            jobs[code], _ = Job.objects.get_or_create(
                code=code,
                defaults={
                    "title": title,
                    "job_family": job_families[family],
                    "job_level": job_levels[level],
                    "employment_category": category,
                },
            )

        restaurant_count = 0
        for area_name, restaurant_names in RESTAURANTS_BY_AREA.items():
            area = area_units[area_name]
            for name in restaurant_names:
                restaurant_count += 1
                number = f"MCD-{restaurant_count:04d}"
                location, created = Location.objects.get_or_create(
                    code=f"LOC-{number}",
                    defaults={
                        "organization_unit": area,
                        "name": f"McDonald's {name}",
                        "location_type": Location.LocationType.RESTAURANT,
                        "city": area_name.split()[-1],
                        "province": "Punjab"
                        if "Lahore" in area_name
                        else ("Sindh" if "Karachi" in area_name else "Islamabad Capital Territory"),
                    },
                )
                restaurant, _ = Restaurant.objects.get_or_create(
                    location=location,
                    defaults={
                        "restaurant_number": number,
                        "operational_status": Restaurant.OperationalStatus.OPERATING,
                    },
                )

                for dept_name in DEPARTMENTS_PER_RESTAURANT:
                    department, _ = Department.objects.get_or_create(
                        code=f"{number}-{dept_name[:3].upper()}",
                        defaults={"name": dept_name, "location": location},
                    )

                    if dept_name == "Kitchen":
                        for job_code in ("REST-MGR", "ASST-MGR", "SHIFT-LEAD", "CREW"):
                            job = jobs[job_code]
                            headcount = next(h for c, _, _, _, _, h in JOBS if c == job_code)
                            Position.objects.get_or_create(
                                code=f"{number}-{job_code}",
                                defaults={
                                    "job": job,
                                    "department": department,
                                    "title": job.title,
                                    "status": Position.Status.ACTIVE,
                                    "headcount_limit": headcount,
                                    "position_type": (
                                        Position.PositionType.MANAGEMENT
                                        if job_code == "REST-MGR"
                                        else Position.PositionType.SUPERVISORY
                                        if job_code in {"ASST-MGR", "SHIFT-LEAD"}
                                        else Position.PositionType.INDIVIDUAL_CONTRIBUTOR
                                    ),
                                },
                            )

        hr_unit = OrganizationUnit.objects.get(company=company, code="BU-HUM")
        Position.objects.get_or_create(
            code="CORP-HR-001",
            defaults={
                "job": jobs["HR-OFFICER"],
                "organization_unit": hr_unit,
                "title": jobs["HR-OFFICER"].title,
                "status": Position.Status.ACTIVE,
                "headcount_limit": 2,
                "position_type": Position.PositionType.INDIVIDUAL_CONTRIBUTOR,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {restaurant_count} restaurants across {len(area_units)} areas."
            )
        )
