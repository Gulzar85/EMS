import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_home_redirects_anonymous_to_login(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_home_renders_for_authenticated_user(client):
    user = UserFactory(email="staff@example.local", password="pw12345!")
    client.force_login(user)
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert b"Dashboard" in response.content


def test_login_page_renders_form(client):
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert b"Email address" in response.content


def test_login_flow_succeeds_with_correct_credentials(client):
    UserFactory(email="login@example.local", password="correct-pw-123")
    response = client.post(
        reverse("accounts:login"),
        {"username": "login@example.local", "password": "correct-pw-123"},
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home")


def test_login_flow_fails_with_wrong_password(client):
    UserFactory(email="login2@example.local", password="correct-pw-123")
    response = client.post(
        reverse("accounts:login"),
        {"username": "login2@example.local", "password": "wrong-password"},
    )
    assert response.status_code == 200  # re-rendered form, not redirected
    assert response.context["form"].errors


def test_logout_requires_post(client):
    user = UserFactory(email="logout@example.local", password="pw12345!")
    client.force_login(user)
    response = client.get(reverse("accounts:logout"))
    assert response.status_code == 405  # Django's LogoutView only accepts POST


def test_logout_via_post_ends_session(client):
    user = UserFactory(email="logout2@example.local", password="pw12345!")
    client.force_login(user)
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    home_response = client.get(reverse("core:home"))
    assert home_response.status_code == 302  # session cleared, redirected to login again


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
def test_custom_404_page_renders_without_debug_traceback():
    response = Client(raise_request_exception=False).get("/this-does-not-exist/")
    assert response.status_code == 404
    assert b"Page not found" in response.content
    assert b"Traceback" not in response.content


def test_custom_403_view_renders_access_denied_page(rf):
    from apps.core.views import ErrorView

    view = ErrorView.as_view(template_name="pages/errors/403.html", status_code=403)
    response = view(rf.get("/anything/"))
    response.render()
    assert response.status_code == 403
    assert b"Access denied" in response.content


def test_custom_500_view_renders_without_traceback(rf):
    from apps.core.views import ErrorView

    view = ErrorView.as_view(template_name="pages/errors/500.html", status_code=500)
    response = view(rf.get("/anything/"))
    response.render()
    assert response.status_code == 500
    assert b"Traceback" not in response.content
