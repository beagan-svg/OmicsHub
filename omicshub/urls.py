import os

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from apps.accounts.forms import LoginForm
from omicshub.health import health

# Where the admin is mounted. It is the one page on this host that can edit users, read
# every queue entry, and activate a config, and "/admin/" is the first path anything
# scanning the tunnel will try, so it is configurable and should not be the default
# anywhere the app is reachable by more than the machine it runs on.
#
# Read from settings when a setting exists, and from the environment otherwise. Templates
# and tests use reverse("admin:index"), so changing it requires one variable.
_admin_url = getattr(settings, "ADMIN_URL", None) or os.environ.get("ADMIN_URL") or "admin"
# Tolerate "ops/", "/ops" and "ops" alike; path() needs exactly one trailing slash and no
# leading one.
ADMIN_PATH = _admin_url.strip("/") + "/"

urlpatterns = [
    path("healthz/", health, name="health"),
    path(ADMIN_PATH, admin.site.urls),
    # Self-registration sits alongside the built-in auth views under the same prefix.
    # Only login and logout are wired up: the rest of django.contrib.auth.urls is the
    # password-reset flow, which needs mail settings and templates this project has not.
    path("accounts/", include("apps.accounts.urls")),
    path("accounts/login/", LoginView.as_view(authentication_form=LoginForm), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("apps.sample_catalog.urls")),
    path("api/", include("apps.workflow_engine.urls")),
    path("api/", include("apps.submission_queue.urls")),
    # Last: the web app owns "" and would otherwise shadow nothing, but keeping it here
    # makes the API and admin prefixes the first thing a reader sees.
    path("", include("apps.web_ui.urls")),
]
