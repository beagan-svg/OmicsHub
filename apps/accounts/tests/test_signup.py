"""Self-registration: who gets an account, and what that account can reach."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

PASSWORD = "correct-horse-battery"


@pytest.mark.django_db
def test_signup_creates_user_and_signs_them_in(client):
    response = client.post(
        reverse("accounts:signup"),
        {"username": "ada", "email": "ada@example.org", "password1": PASSWORD, "password2": PASSWORD},
    )

    user = User.objects.get(username="ada")
    assert user.email == "ada@example.org"
    # Redirected into the app, not back to the login page.
    assert response.status_code == 302
    assert response.url == reverse("web:dashboard")
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_registered_user_gets_no_admin_access(client):
    """Create a user without granting admin access."""
    client.post(
        reverse("accounts:signup"),
        {"username": "ada", "password1": PASSWORD, "password2": PASSWORD},
    )

    user = User.objects.get(username="ada")
    assert user.is_staff is False
    assert user.is_superuser is False
    # Django's admin bounces non-staff to its own login rather than serving the index.
    # Reversed rather than spelled out: the admin is mounted at a configurable path.
    assert client.get(reverse("admin:index"), follow=False).status_code == 302


@pytest.mark.django_db
def test_password_validators_apply(client):
    response = client.post(
        reverse("accounts:signup"),
        {"username": "ada", "password1": "password", "password2": "password"},
    )

    assert response.status_code == 200
    assert not User.objects.filter(username="ada").exists()
    assert response.context["form"].errors["password2"]


@pytest.mark.django_db
def test_mismatched_passwords_are_rejected(client):
    response = client.post(
        reverse("accounts:signup"),
        {"username": "ada", "password1": PASSWORD, "password2": PASSWORD + "x"},
    )

    assert response.status_code == 200
    assert not User.objects.filter(username="ada").exists()


@pytest.mark.django_db
def test_duplicate_username_is_rejected(client):
    User.objects.create_user(username="ada", password=PASSWORD)

    response = client.post(
        reverse("accounts:signup"),
        {"username": "ada", "password1": PASSWORD, "password2": PASSWORD},
    )

    assert response.status_code == 200
    assert User.objects.filter(username="ada").count() == 1


@pytest.mark.django_db
def test_signed_in_user_is_redirected_away(client):
    User.objects.create_user(username="ada", password=PASSWORD)
    client.login(username="ada", password=PASSWORD)

    response = client.get(reverse("accounts:signup"))

    assert response.status_code == 302
    assert response.url == reverse("web:dashboard")


@pytest.mark.django_db
def test_login_page_offers_registration(client):
    """Show a registration link on the login page."""
    response = client.get(reverse("login"))

    assert reverse("accounts:signup") in response.content.decode()
