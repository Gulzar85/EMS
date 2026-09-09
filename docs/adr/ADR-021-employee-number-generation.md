# ADR-021: Employee Number Generation Strategy

Status: Accepted (Phase 04)

## Context

`employee_number` is the business identifier for an `Employee` — searchable, displayed everywhere, and must never be derived from the integer primary key (Phase 04 brief §8-§9): a PK is an internal implementation detail (its value depends on insertion order, can be renumbered by a restore, and leaks row-count information), while a business identifier must be a stable, intentional fact the business controls.

Concurrent employee creation (two HR staff submitting new-hire forms around the same moment) must never produce a duplicate number, and must not rely on a Python-level "read the max, add one, save" race.

## Decision

A single-row counter table, `EmployeeNumberSequence` (`apps/employees/models/sequence.py`), holding one integer `last_value`. `EmployeeNumberService.generate()` (`apps/employees/services/number.py`) wraps the increment in `transaction.atomic()` with `.select_for_update()`, so concurrent callers serialize on the row lock rather than racing:

```python
@staticmethod
@transaction.atomic
def generate() -> str:
    sequence, _ = EmployeeNumberSequence.objects.select_for_update().get_or_create(pk=1)
    sequence.last_value += 1
    sequence.save(update_fields=["last_value"])
    return f"{settings.EMPLOYEE_NUMBER_PREFIX}{sequence.last_value:0{settings.EMPLOYEE_NUMBER_PADDING}d}"
```

Format is configurable via `EMPLOYEE_NUMBER_PREFIX` (default `"EMP-"`) and `EMPLOYEE_NUMBER_PADDING` (default `6`) in settings — e.g. `EMP-000001` — so a future change in numbering convention (a per-region prefix, different padding) is a settings change, not a code change.

## Alternatives considered

- **A raw PostgreSQL `SEQUENCE`** (`nextval()`): marginally faster under very high concurrency, but ties generation to a Postgres-specific mechanism outside Django's ORM, is harder to test/mock, and offers no real benefit at McDonald's Pakistan's actual hiring throughput (nowhere near a rate where row-level locking on one counter row becomes a bottleneck).
- **`str(employee.pk)`**: explicitly rejected by the brief and by this project's own database conventions — the PK must stay an internal detail.
- **UUID-based numbers**: not human-usable for a field HR staff read, write, and search by daily.

## Verification

`apps/employees/tests/test_services.py::test_employee_number_generation_is_concurrency_safe` spins up 10 threads (each on its own DB connection, using `@pytest.mark.django_db(transaction=True)` so the test actually commits across threads instead of relying on rolled-back transaction isolation) calling `generate()` concurrently and asserts all 10 results are unique with no errors.
