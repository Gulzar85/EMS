"""Cross-cutting tests for the health endpoints — see apps/core/views.py.

Covers the three-way content negotiation (JSON for monitors/default,
HTML for real browser navigation, an HTMX fragment for the dashboard's
"Refresh status" button) plus the live/ready split.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_live_endpoint_does_not_touch_database(client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("health/live/ must not touch the database")

    monkeypatch.setattr("django.db.connection.ensure_connection", fail_if_called)
    response = client.get(reverse("core:health-live"))
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_endpoint_returns_json_by_default(client):
    # No explicit Accept header — must NOT fall back to HTML (see the
    # comment in apps/core/views.py about "*/*" matching text/html).
    response = client.get(reverse("core:health-ready"))
    assert response.headers["Content-Type"].startswith("application/json")


def test_ready_endpoint_json_body_has_database_check(client):
    response = client.get(reverse("core:health-ready"))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"


def test_ready_endpoint_renders_html_for_browsers(client):
    response = client.get(
        reverse("core:health-ready"), headers={"Accept": "text/html,application/xhtml+xml"}
    )
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/html")
    assert b"System status" in response.content


def test_ready_endpoint_renders_fragment_for_htmx(client):
    response = client.get(reverse("core:health-ready"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"<html" not in response.content.lower()
    assert b"health-status" in response.content


def test_health_alias_matches_ready(client):
    ready = client.get(reverse("core:health-ready"))
    health = client.get(reverse("core:health"))
    assert ready.json() == health.json()
