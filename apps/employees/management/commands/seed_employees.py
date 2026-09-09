"""Idempotent demo seed data — safe to run repeatedly. Builds on top of
`seed_organization` (Phase 03): for each seeded restaurant, hires a small,
realistic reporting chain (Restaurant Manager -> Assistant Manager ->
Shift Leaders -> Crew Members) into the seeded positions, plus one HR
Officer at corporate. Every name is fictional — no real employee data
(Phase 04 brief §85).
"""

from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.employees.models import Employee
from apps.employees.services import (
    EmployeeAssignmentService,
    EmployeeLifecycleService,
    EmployeeManagerService,
    EmployeeService,
)
from apps.organization.models import Position

FIRST_NAMES = [
    "Ahmed", "Ayesha", "Bilal", "Sana", "Usman", "Hina", "Fahad", "Mahnoor",
    "Hamza", "Zainab", "Imran", "Rabia", "Kashif", "Farah", "Junaid", "Alina",
    "Waqas", "Nida", "Adeel", "Sadia", "Tariq", "Iqra", "Salman", "Mehwish",
]
LAST_NAMES = [
    "Khan", "Malik", "Butt", "Cheema", "Raza", "Iqbal", "Farooq", "Siddiqui",
    "Shaikh", "Qureshi", "Baig", "Chaudhry", "Abbasi", "Awan", "Zafar", "Rashid",
]

_JOINING_BASE = dt.date(2023, 1, 1)


class Command(BaseCommand):
    help = "Seed realistic sample employee data on top of seed_organization (no real employee data)."

    @transaction.atomic
    def handle(self, *args, **options):
        if not Position.objects.filter(status=Position.Status.ACTIVE).exists():
            raise CommandError("Run `manage.py seed_organization` first — no active positions found.")

        self._name_index = 0
        created_count = 0

        # Restaurant position codes look like "MCD-0001-REST-MGR" — the
        # restaurant number is always the first two hyphen-segments.
        restaurant_numbers = sorted(
            {
                "-".join(code.split("-")[:2])
                for code in Position.objects.filter(department__isnull=False).values_list(
                    "code", flat=True
                )
            }
        )

        for number in restaurant_numbers:
            created_count += self._seed_restaurant(number)

        hr_position = Position.objects.filter(code="CORP-HR-001").first()
        if hr_position and not Employee.objects.filter(current_position=hr_position).exists():
            self._hire(hr_position, manager=None)
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} employees."))

    def _seed_restaurant(self, number: str) -> int:
        manager_position = Position.objects.filter(code=f"{number}-REST-MGR").first()
        if not manager_position:
            return 0
        if Employee.objects.filter(current_position=manager_position).exists():
            return 0  # already seeded this restaurant

        created = 0
        manager = self._hire(manager_position, manager=None)
        created += 1

        assistant_position = Position.objects.filter(code=f"{number}-ASST-MGR").first()
        assistant = None
        if assistant_position:
            assistant = self._hire(assistant_position, manager=manager)
            created += 1

        shift_lead_position = Position.objects.filter(code=f"{number}-SHIFT-LEAD").first()
        shift_leads: list[Employee] = []
        if shift_lead_position:
            for _ in range(min(2, shift_lead_position.headcount_limit)):
                lead = self._hire(shift_lead_position, manager=assistant or manager)
                shift_leads.append(lead)
                created += 1

        crew_position = Position.objects.filter(code=f"{number}-CREW").first()
        if crew_position and shift_leads:
            for i in range(min(4, crew_position.headcount_limit)):
                self._hire(crew_position, manager=shift_leads[i % len(shift_leads)])
                created += 1

        return created

    def _hire(self, position: Position, *, manager: Employee | None) -> Employee:
        first = FIRST_NAMES[self._name_index % len(FIRST_NAMES)]
        last = LAST_NAMES[(self._name_index * 7) % len(LAST_NAMES)]
        self._name_index += 1
        suffix = self._name_index
        joining_date = _JOINING_BASE + dt.timedelta(days=suffix * 11)

        employee = EmployeeService.create_employee(
            actor=None,
            first_name=first,
            last_name=last,
            nationality="Pakistani",
            work_email=f"{first.lower()}.{last.lower()}{suffix}@mcdonalds.com.pk",
            mobile_number=f"0300{1000000 + suffix:07d}",
            city="Lahore",
            province="Punjab",
            country="Pakistan",
            joining_date=joining_date,
            employment_type=position.job.employment_category,
        )
        EmployeeLifecycleService.activate(employee=employee, actor=None)
        EmployeeAssignmentService.assign_position(
            employee=employee,
            position=position,
            assignment_type="primary",
            is_primary=True,
            start_date=joining_date,
            actor=None,
        )
        if manager is not None:
            EmployeeManagerService.assign_manager(
                employee=employee, manager=manager, start_date=joining_date, actor=None
            )
        return employee
