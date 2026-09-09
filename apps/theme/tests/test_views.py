import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.theme.models import Theme, ThemeVersion
from apps.theme.tests.factories import ThemeFactory, ThemeVersionFactory
from apps.theme.validation import COLOR_TOKENS

pytestmark = pytest.mark.django_db

ALL_THEME_PERMS = [
    "view_theme",
    "add_theme",
    "change_theme",
    "delete_theme",
    "publish_theme",
    "rollback_theme",
    "activate_theme",
]


def _permissioned_user(*codenames):
    user = UserFactory()
    perms = Permission.objects.filter(content_type__app_label="theme", codename__in=codenames)
    user.user_permissions.add(*perms)
    return user


def _studio_post_data(theme):
    from apps.theme.validation import DEFAULT_THEME_TOKENS

    colors = DEFAULT_THEME_TOKENS["colors"]
    data = {
        "font_family": DEFAULT_THEME_TOKENS["typography"]["font_family"],
        "font_size_base": DEFAULT_THEME_TOKENS["typography"]["font_size_base"],
    }
    for name in COLOR_TOKENS:
        data[f"color_{name}_light"] = colors[name]["light"]
        data[f"color_{name}_dark"] = colors[name]["dark"]
    for name in ("sm", "md", "lg"):
        data[f"radius_{name}"] = DEFAULT_THEME_TOKENS["radius"][name]
    return data


# --- Authentication / authorization -----------------------------------------


def test_list_view_redirects_anonymous_to_login(client):
    response = client.get(reverse("theme:list"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_list_view_forbidden_without_permission(client):
    user = UserFactory()  # no theme permissions
    client.force_login(user)
    response = client.get(reverse("theme:list"))
    assert response.status_code == 403


def test_list_view_ok_with_permission(client):
    user = _permissioned_user("view_theme")
    client.force_login(user)
    response = client.get(reverse("theme:list"))
    assert response.status_code == 200


@pytest.mark.parametrize(
    "url_name,perm",
    [
        ("create", "add_theme"),
        ("publish", "publish_theme"),
        ("rollback", "rollback_theme"),
        ("activate", "activate_theme"),
        ("duplicate", "add_theme"),
        ("delete", "delete_theme"),
    ],
)
def test_action_views_require_their_specific_permission(client, url_name, perm):
    """A user who can merely view/edit must not be able to publish, roll
    back, activate, duplicate, or delete — confirms permissions are
    per-action, not a single blanket check (Phase 02 plan §13)."""
    theme = ThemeFactory(is_active=False)
    ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    user = _permissioned_user("view_theme", "change_theme")  # deliberately NOT `perm`
    client.force_login(user)

    kwargs = {"public_id": theme.public_id} if url_name != "create" else {}
    url = reverse(f"theme:{url_name}", kwargs=kwargs)
    response = client.get(url)
    assert response.status_code == 403


# --- CRUD lifecycle via the test client --------------------------------------


def test_create_theme_via_post(client):
    user = _permissioned_user("add_theme")
    client.force_login(user)

    response = client.post(
        reverse("theme:create"), {"name": "Holiday Promo", "description": "Festive colors"}
    )

    theme = Theme.objects.get(name="Holiday Promo")
    assert response.status_code == 302
    assert response.url == reverse("theme:studio", kwargs={"public_id": theme.public_id})
    assert theme.versions.count() == 1


def test_get_never_mutates_on_publish_url(client):
    """A GET on a destructive/state-changing action URL must only ever show
    a confirmation form — never perform the action (Phase 02 plan §15)."""
    theme = ThemeFactory(is_active=False)
    ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.DRAFT)
    user = _permissioned_user(*ALL_THEME_PERMS)
    client.force_login(user)

    client.get(reverse("theme:publish", kwargs={"public_id": theme.public_id}))

    theme.refresh_from_db()
    assert theme.is_active is False  # unchanged — only the POST publishes


def test_studio_saves_a_new_draft(client):
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED)
    user = _permissioned_user("view_theme", "change_theme")
    client.force_login(user)

    data = _studio_post_data(theme)
    data["color_brand_light"] = "#0057b8"
    response = client.post(reverse("theme:studio", kwargs={"public_id": theme.public_id}), data)

    assert response.status_code == 302
    draft = theme.versions.get(status=ThemeVersion.Status.DRAFT)
    assert draft.tokens["colors"]["brand"]["light"] == "#0057b8"


def test_studio_invalid_submission_rerenders_form_with_errors(client):
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1)
    user = _permissioned_user("view_theme", "change_theme")
    client.force_login(user)

    data = _studio_post_data(theme)
    data["color_brand_light"] = "not-a-color"
    response = client.post(reverse("theme:studio", kwargs={"public_id": theme.public_id}), data)

    assert response.status_code == 200  # re-rendered, not redirected
    assert response.context["form"].errors


def test_publish_then_rollback_full_cycle(client):
    theme = ThemeFactory(is_active=False)
    v1 = ThemeVersionFactory(theme=theme, version_number=1, status=ThemeVersion.Status.DRAFT)
    user = _permissioned_user(*ALL_THEME_PERMS)
    client.force_login(user)

    client.post(
        reverse("theme:publish", kwargs={"public_id": theme.public_id}), {"reason": "go live"}
    )
    theme.refresh_from_db()
    assert theme.is_active is True
    assert theme.active_version_id == v1.pk

    # publish a second draft
    data = _studio_post_data(theme)
    data["color_brand_light"] = "#0057b8"
    client.post(reverse("theme:studio", kwargs={"public_id": theme.public_id}), data)
    v2 = theme.versions.get(status=ThemeVersion.Status.DRAFT)
    client.post(reverse("theme:publish", kwargs={"public_id": theme.public_id}), {"reason": ""})
    theme.refresh_from_db()
    assert theme.active_version_id == v2.pk

    # roll back to v1
    client.post(
        reverse("theme:rollback", kwargs={"public_id": theme.public_id}),
        {"target_version": v1.pk, "reason": "revert"},
    )
    theme.refresh_from_db()
    assert theme.active_version_id == v1.pk


def test_delete_requires_post_not_get(client):
    theme = ThemeFactory(is_active=False)
    user = _permissioned_user("delete_theme", "view_theme")
    client.force_login(user)

    get_response = client.get(reverse("theme:delete", kwargs={"public_id": theme.public_id}))
    assert get_response.status_code == 200  # confirmation page only
    assert Theme.objects.filter(pk=theme.pk).exists()

    post_response = client.post(reverse("theme:delete", kwargs={"public_id": theme.public_id}))
    assert post_response.status_code == 302
    assert not Theme.objects.filter(pk=theme.pk).exists()


# --- HTMX -------------------------------------------------------------------


def test_list_view_htmx_request_returns_partial_without_full_page_chrome(client):
    user = _permissioned_user("view_theme")
    client.force_login(user)

    response = client.get(reverse("theme:list"), headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert b"<html" not in response.content.lower()
    assert b"<nav" not in response.content.lower() or b"Pagination" not in response.content


def test_studio_htmx_invalid_submission_returns_partial(client):
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1)
    user = _permissioned_user("view_theme", "change_theme")
    client.force_login(user)

    data = _studio_post_data(theme)
    data["color_brand_light"] = "bad"
    response = client.post(
        reverse("theme:studio", kwargs={"public_id": theme.public_id}),
        data,
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b"<html" not in response.content.lower()


def test_studio_htmx_valid_submission_returns_hx_redirect_header(client):
    theme = ThemeFactory()
    ThemeVersionFactory(theme=theme, version_number=1)
    user = _permissioned_user("view_theme", "change_theme")
    client.force_login(user)

    data = _studio_post_data(theme)
    response = client.post(
        reverse("theme:studio", kwargs={"public_id": theme.public_id}),
        data,
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers


# --- theme.css (public) ------------------------------------------------------


def test_theme_css_is_public_and_reflects_active_theme(client):
    theme = ThemeFactory(is_active=True)
    version = ThemeVersionFactory(
        theme=theme, version_number=1, status=ThemeVersion.Status.PUBLISHED
    )
    theme.active_version = version
    theme.save(update_fields=["active_version"])

    response = client.get(reverse("theme-css"))  # no login at all

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/css"
    assert version.tokens["colors"]["brand"]["light"].upper() in response.content.decode().upper()


def test_theme_css_empty_when_no_active_theme(client):
    response = client.get(reverse("theme-css"))
    assert response.status_code == 200
    assert response.content.decode().strip() == ""


# --- Appearance preference ---------------------------------------------------


def test_appearance_update_requires_login(client):
    response = client.post(reverse("appearance-update"), {"appearance": "dark"})
    assert response.status_code == 302


def test_appearance_update_persists_preference(client):
    from apps.theme.models import UserThemePreference

    user = UserFactory()
    client.force_login(user)

    response = client.post(reverse("appearance-update"), {"appearance": "dark"})

    assert response.status_code == 204
    assert UserThemePreference.objects.get(user=user).appearance == "dark"


def test_appearance_update_rejects_invalid_choice(client):
    user = UserFactory()
    client.force_login(user)
    response = client.post(reverse("appearance-update"), {"appearance": "purple"})
    assert response.status_code == 400
