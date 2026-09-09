"""Shared validation helpers for the employees app.

`assert_no_manager_cycle` mirrors `apps.organization.validators.assert_no_cycle`
but cannot reuse it directly: that helper walks a plain self-FK
(`OrganizationUnit.parent`, `Position.reports_to`), while "who currently
manages this employee" is derived from `EmployeeManagerAssignment` rows
(the historical join table), not a plain field — see docs/adr/ADR-022.
"""

from __future__ import annotations

import os

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

ALLOWED_PROFILE_PHOTO_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ALLOWED_PROFILE_PHOTO_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def assert_no_manager_cycle(employee, candidate_manager) -> None:
    """Raise ValidationError if making `candidate_manager` the manager of
    `employee` would create a reporting cycle. Walks the *current* manager
    chain (via Employee.current_manager, the synchronized read-model — see
    docs/adr/ADR-024), not the full assignment history.
    """
    if candidate_manager is None:
        return
    if employee.pk is not None and candidate_manager.pk == employee.pk:
        raise ValidationError({"manager": "An employee cannot be their own manager."})

    seen: set[int] = set()
    current = candidate_manager
    while current is not None:
        if employee.pk is not None and current.pk == employee.pk:
            raise ValidationError(
                {"manager": "This change would create a circular reporting relationship."}
            )
        if current.pk in seen:
            break  # already-corrupt data upstream — stop rather than loop forever
        seen.add(current.pk)
        current = current.current_manager


def validate_profile_photo(file: UploadedFile) -> None:
    """Defense-in-depth for an uploaded image: never trust the client-supplied
    extension or `content_type` header alone (both are attacker-controlled);
    require the extension AND the browser-reported content type to both be
    on the allow-list, then sniff the actual bytes with Pillow.
    """
    from django.conf import settings

    extension = os.path.splitext(file.name or "")[1].lower()
    if extension not in ALLOWED_PROFILE_PHOTO_EXTENSIONS:
        raise ValidationError("Profile photo must be a JPG, PNG, or WEBP file.")
    if file.content_type not in ALLOWED_PROFILE_PHOTO_CONTENT_TYPES:
        raise ValidationError("Profile photo must be a JPG, PNG, or WEBP file.")
    if file.size > settings.EMPLOYEE_PROFILE_PHOTO_MAX_BYTES:
        max_mb = settings.EMPLOYEE_PROFILE_PHOTO_MAX_BYTES / (1024 * 1024)
        raise ValidationError(f"Profile photo must be smaller than {max_mb:.0f} MB.")

    from PIL import Image

    try:
        image = Image.open(file)
        image.verify()
    except Exception as exc:
        raise ValidationError("This file is not a valid image.") from exc
    finally:
        file.seek(0)
