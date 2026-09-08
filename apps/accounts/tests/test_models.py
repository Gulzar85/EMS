import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.db.utils import DataError

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_create_user_normalizes_email_domain():
    user = User.objects.create_user(email="Someone@EXAMPLE.com", password="pw12345!")
    assert user.email == "Someone@example.com"


def test_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="pw12345!")


def test_create_user_defaults_are_safe():
    user = User.objects.create_user(email="a@example.local", password="pw12345!")
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


def test_password_is_hashed_not_plaintext():
    user = User.objects.create_user(email="a@example.local", password="pw12345!")
    assert user.password != "pw12345!"
    assert user.check_password("pw12345!")


def test_email_uniqueness_enforced():
    User.objects.create_user(email="dup@example.local", password="pw12345!")
    with pytest.raises((IntegrityError, DataError)):
        User.objects.create_user(email="dup@example.local", password="pw12345!")


def test_create_superuser_sets_staff_and_superuser():
    admin = User.objects.create_superuser(email="admin@example.local", password="pw12345!")
    assert admin.is_staff is True
    assert admin.is_superuser is True


def test_create_superuser_rejects_is_staff_false():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="admin@example.local", password="pw12345!", is_staff=False
        )


def test_create_superuser_rejects_is_superuser_false():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="admin@example.local", password="pw12345!", is_superuser=False
        )


def test_inactive_user_cannot_authenticate():
    UserFactory(email="inactive@example.local", is_active=False, password="pw12345!")
    assert authenticate(username="inactive@example.local", password="pw12345!") is None


def test_active_user_can_authenticate():
    UserFactory(email="active@example.local", password="pw12345!")
    assert authenticate(username="active@example.local", password="pw12345!") is not None


def test_str_returns_email():
    user = UserFactory(email="str@example.local")
    assert str(user) == "str@example.local"


def test_get_full_name_falls_back_to_email():
    user = UserFactory(email="noname@example.local", first_name="", last_name="")
    assert user.get_full_name() == "noname@example.local"


def test_get_full_name_combines_first_and_last():
    user = UserFactory(first_name="Ada", last_name="Lovelace")
    assert user.get_full_name() == "Ada Lovelace"
