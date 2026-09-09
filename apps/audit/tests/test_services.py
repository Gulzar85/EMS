import pytest

from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.theme.tests.factories import ThemeFactory

pytestmark = pytest.mark.django_db


def test_record_captures_actor_action_and_entity():
    actor = UserFactory()
    # User has no public_id (see apps/accounts/models.py) — record() must
    # fall back to the entity's plain pk in that case.
    entity = UserFactory()

    log = record(actor=actor, action="theme.published", entity=entity, after={"x": 1})

    assert log.actor == actor
    assert log.action == "theme.published"
    assert log.entity_type == "User"
    assert log.entity_id == str(entity.pk)
    assert log.after == {"x": 1}


def test_record_uses_public_id_when_entity_has_one():
    theme = ThemeFactory()
    log = record(actor=None, action="theme.created", entity=theme)
    assert log.entity_type == "Theme"
    assert log.entity_id == str(theme.public_id)
    assert log.entity_id != str(theme.pk)


def test_record_persists_before_after_and_reason():
    log = record(
        actor=None,
        action="theme.rolled_back",
        entity=UserFactory(),
        before={"version": 2},
        after={"version": 1},
        reason="Bad color choice",
    )
    fetched = AuditLog.objects.get(pk=log.pk)
    assert fetched.before == {"version": 2}
    assert fetched.after == {"version": 1}
    assert fetched.reason == "Bad color choice"


def test_record_allows_null_actor_for_system_actions():
    log = record(actor=None, action="theme.seeded", entity=UserFactory())
    assert log.actor is None
