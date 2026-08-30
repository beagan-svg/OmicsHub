"""Configure the test suite without Docker environment files."""

import os

os.environ.setdefault("SECRET_KEY", "test-only-not-a-real-secret")
os.environ.setdefault("DATABASE_URL", "postgres://omicshub:omicshub@localhost:5432/omicshub")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("OCS_ENV_BASE", "test")
os.environ.setdefault("OCS_AWS_REGION", "us-west-2")
os.environ["ENVIRONMENT"] = "test"
# Obviously-fake, valid-format Fernet key: real key material must never appear in test
# settings, but Fernet(key) itself must not raise, so this is a deterministic throwaway.
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = "2fPuizO90Xj1avGhT1E3AAVDfKZT1T1cgccHh5p_6a8="

# Assigned, not `setdefault`: a developer with a real DSN in their .env would otherwise
# have the suite initialise Sentry and report their own test failures as production errors.
os.environ["SENTRY_DSN"] = ""

from .base import *  # noqa: E402, F403
from .base import MIDDLEWARE as BASE_MIDDLEWARE

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Tests render templates but never serve static files. WhiteNoise checks STATIC_ROOT when
# middleware loads, which adds a warning to every request because collectstatic is not a test
# setup step.
MIDDLEWARE = [
    middleware for middleware in BASE_MIDDLEWARE if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]

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

DEBUG = False
