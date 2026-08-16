"""Settings for the test suite.

Defaults are set before importing base so the suite runs without a .env file. The database
still points at Postgres: the queue claim uses SELECT ... FOR UPDATE SKIP LOCKED, which
SQLite does not implement.

.env is read here rather than only in base, because `setdefault` below fills a variable
base's own read would then decline to overwrite. Without this the DATABASE_URL fallback
wins over the real one and the suite runs against whatever that string happens to name.
which after the database password changed meant every test erroring on authentication.
"""

import os
from pathlib import Path

import environ

environ.Env.read_env(Path(__file__).resolve().parents[2] / ".env")

os.environ.setdefault("SECRET_KEY", "test-only-not-a-real-secret")
os.environ.setdefault("DATABASE_URL", "postgres://omicshub:omicshub@localhost:5432/omicshub")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("OCS_ENV_BASE", "test")
os.environ.setdefault("OCS_AWS_REGION", "us-west-2")

# Assigned, not `setdefault`: a developer with a real DSN in their .env would otherwise
# have the suite initialise Sentry and report their own test failures as production errors.
os.environ["SENTRY_DSN"] = ""

from .base import *  # noqa: E402, F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# No persistent connections under test. base.py keeps them for 60 seconds, which is right
# for a server and wrong here: a held connection is still open when the runner tries to
# create or drop the test database, which fails intermittently and takes the whole session
# with it rather than one test.
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = False  # noqa: F405

# Local memory rather than Redis: the suite runs in one process, so a per-process cache is
# a faithful stand-in for the capacity hold, and the tests should not need a Redis to run.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# The manifest backend resolves {% static %} through a file collectstatic writes, which the
# suite has no reason to run. Rendering a template must not depend on a build step.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
