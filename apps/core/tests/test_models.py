"""Abstract base models have no concrete table yet (no domain app exists),
so these tests verify the field contracts future models will inherit rather
than round-tripping through the database.
"""

import uuid

from apps.core.models import PublicIDModel, TimeStampedModel


def test_timestamped_model_is_abstract():
    assert TimeStampedModel._meta.abstract is True


def test_timestamped_model_fields():
    created_at = TimeStampedModel._meta.get_field("created_at")
    updated_at = TimeStampedModel._meta.get_field("updated_at")
    assert created_at.auto_now_add is True
    assert updated_at.auto_now is True


def test_public_id_model_is_abstract():
    assert PublicIDModel._meta.abstract is True


def test_public_id_model_field_is_unique_uuid():
    field = PublicIDModel._meta.get_field("public_id")
    assert field.unique is True
    assert field.editable is False
    assert field.default is uuid.uuid4
