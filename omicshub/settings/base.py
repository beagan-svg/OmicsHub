import logging
import os
from pathlib import Path

import environ
from celery.schedules import crontab
from django.contrib.messages import constants as message_constants

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts",
    "apps.catalog",
    "apps.workflows",
    "apps.queueing",
    "apps.web",
]

MIDDLEWARE = [
    # First, so that everything after it — including the security middleware's own
    # rejections — logs under the request's correlation id.
    "omicshub.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Serves the admin's CSS and JS. Django's own static serving only runs with DEBUG on,
    # and DEBUG must be off whenever this is reachable outside the machine.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "omicshub.urls"
WSGI_APPLICATION = "omicshub.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.web.context_processors.cart",
            ],
        },
    },
]

# Redis, not the per-process default. The only thing in the cache is the submission
# worker's capacity hold, and a hold that lives in one process's memory is not a hold —
# it would vanish on restart and would not be seen by a second worker. Its own database,
# so a `FLUSHDB` on the cache never touches the Celery broker.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", default="redis://localhost:6379/1"),
    }
}

DATABASES = {"default": env.db("DATABASE_URL")}
# Reuse connections instead of reconnecting per request. The health check costs a ping but
# turns a connection dropped by a database restart into a retry rather than a random
# OperationalError for whoever gets that connection next.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "web:dashboard"
LOGOUT_REDIRECT_URL = "login"
# Django's error level is "error"; Bootstrap's alert class is "danger". Remapping here
# keeps the base template's message loop a plain alert-{{ level_tag }}.
MESSAGE_TAGS = {message_constants.ERROR: "danger"}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "omicshub.exception_handler.api_exception_handler",
}

# --- OCS ------------------------------------------------------------------
# Every OCS DynamoDB table is named "<env base>-<table>", e.g. "prod-fastq-metadata".
OCS_ENV_BASE = env("OCS_ENV_BASE")
OCS_AWS_REGION = env("OCS_AWS_REGION")
# Named AWS profile for the DynamoDB reads and the `ocs` CLI. Left empty, boto3 falls back
# to its usual chain (environment variables, then the instance role). Access keys
# themselves are never read from Django settings — see AWS credentials in the README.
AWS_PROFILE = env("AWS_PROFILE", default="")

# Credentials file holding that profile. Pointing this away from ~/.aws/credentials keeps
# the app's long-lived key out of the machine-wide file, so it is reachable only from this
# process and the `ocs` subprocess it starts — everything else on the machine keeps using
# the SSO profiles in ~/.aws/config.
AWS_SHARED_CREDENTIALS_FILE = env("AWS_SHARED_CREDENTIALS_FILE", default="")
if AWS_SHARED_CREDENTIALS_FILE:
    # botocore takes this from the environment. Setting it here covers both in-process
    # boto3 and the CLI subprocess, which inherits this environment.
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = AWS_SHARED_CREDENTIALS_FILE
# The `ocs` executable used to submit alignment and post-alignment demands. Submission is
# the only thing the CLI is used for; everything else reads DynamoDB directly.
OCS_CLI_PATH = env("OCS_CLI_PATH", default="ocs")
# Colon-separated paths the `ocs` CLI needs on PYTHONPATH, mirroring what the interactive
# `activateocs` shell function exports. A worker is not a login shell and inherits none of
# it, so the value is passed explicitly to the subprocess.
OCS_CLI_PYTHONPATH = env("OCS_CLI_PYTHONPATH", default="")
# Timeout for a single `ocs` submission call, in seconds.
OCS_CLI_TIMEOUT = env.int("OCS_CLI_TIMEOUT", default=300)

# --- Celery ---------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_TASK_TIME_LIMIT = 900
CELERY_TASK_SOFT_TIME_LIMIT = 870
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# Submissions run on their own queue with a single worker process, so the global OCS job
# limit and the per-config `spacing` between submissions are both actually enforced.
# Celery's own default queue is named "celery"; the workers are run as `-Q default` and
# `-Q submissions`, so without this every unrouted task — both sweeps and the reconciler —
# is published to a queue nobody consumes and silently never runs.
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.queueing.tasks.process_next_queue_entry": {"queue": "submissions"},
}
CELERY_BEAT_SCHEDULE = {
    # The submission chain re-queues itself; this restarts it when the queue has been
    # idle, and is a cheap no-op when there is nothing pending. It is also the only thing
    # that retries after the OCS job limit is hit — the task does not schedule its own
    # retry, so `job_settings.poll_interval_hours` is honoured through the capacity hold
    # in apps/queueing/tasks.py instead.
    "process-queue": {
        "task": "apps.queueing.tasks.process_next_queue_entry",
        "schedule": 60.0,
    },
    # Sweeps fastq-history and demand-registry — a few seconds each — so the dashboard's
    # ingest/alignment/post-QC columns are never more than this far behind OCS.
    "sync-stage-statuses": {
        "task": "apps.catalog.tasks.sync_all_stage_statuses",
        "schedule": env.int("STAGE_STATUS_SYNC_SECONDS", default=300),
    },
    # Re-mirrors half a million metadata rows, which takes minutes, so it runs nightly.
    # A batch needed sooner is synced on demand from the dashboard.
    "sync-metadata": {
        "task": "apps.catalog.tasks.sync_all_metadata",
        "schedule": crontab(hour=3, minute=0),
    },
    # Surfaces submissions a dying worker left mid-flight; without it they stay invisible.
    "reconcile-stranded-submissions": {
        "task": "apps.queueing.tasks.reconcile_stranded_submissions",
        "schedule": 600.0,
    },
}

# --- Logging --------------------------------------------------------------
# One handler, to stdout, in one format. The containers' output is picked up by a log
# agent, so a file handler would only put the lines somewhere the agent is not looking, and
# rotation would be this process's problem rather than the platform's. Chapter 6's advice
# that logs be "easy to parse by logging agents" is what the fixed field order is for:
# timestamp, level, pid, logger, correlation id, then the message.
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
APP_LOG_LEVEL = env("APP_LOG_LEVEL", default=LOG_LEVEL)

# Named one by one rather than as a single "apps" parent so each can be turned up on its
# own — LOG_LEVEL_CATALOG=DEBUG to watch a sweep, without the submission worker's chatter.
# apps.ocs is in here too: it is not an installed app, but it is where the CLI logs from.
_APP_LOGGERS = ["accounts", "catalog", "ocs", "queueing", "web", "workflows"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "omicshub.logging_filters.RequestIDFilter"},
        "redact_emails": {"()": "omicshub.logging_filters.EmailRedactingFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {process:d} {name} [{request_id}] {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            # Explicit: StreamHandler defaults to stderr, which makes every INFO line look
            # like a fault to anything that separates the two streams.
            "stream": "ext://sys.stdout",
            "formatter": "verbose",
            # On the handler, not on the loggers: a filter attached to a logger only runs
            # for records created on that logger, so records propagating up from a child
            # would skip the redaction. Everything reaches this handler.
            "filters": ["request_id", "redact_emails"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # No handlers, propagate: Django's own default gives this logger a mail_admins
        # handler, and Chapter 6 is explicit that logs should not be shipped by email.
        # Unhandled 500s reach the root console handler here, and Sentry separately.
        "django": {"handlers": [], "level": LOG_LEVEL, "propagate": True},
        **{
            f"apps.{name}": {
                "handlers": [],
                "level": env(f"LOG_LEVEL_{name.upper()}", default=APP_LOG_LEVEL),
                "propagate": True,
            }
            for name in _APP_LOGGERS
        },
    },
}

# --- Error monitoring -----------------------------------------------------
# Chapter 14: "A lot of beginners still use logs to detect raised exceptions. Error
# monitoring tools are lifelines to detect any production exceptions raised." Logging says
# what the system did; Sentry says what broke, with the input that broke it.
#
# Initialised only when a DSN is present, so a developer machine and CI behave exactly as
# they did before and no DSN is ever committed.
ENVIRONMENT = env(
    "ENVIRONMENT",
    default=os.environ.get("DJANGO_SETTINGS_MODULE", "").rsplit(".", 1)[-1] or "unknown",
)
# Sourced from the build rather than computed here: there is no git checkout in the image.
# Without it Sentry still works, it just cannot tell you which deploy introduced a
# regression, and cannot map a frame back to a commit.
SENTRY_RELEASE = env("SENTRY_RELEASE", default=env("GIT_SHA", default=""))
SENTRY_DSN = env("SENTRY_DSN", default="")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    from omicshub.logging_filters import scrub_event

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENVIRONMENT,
        release=SENTRY_RELEASE or None,
        integrations=[
            DjangoIntegration(),
            # Tasks are where the actual work happens; an exception in the submission
            # worker is invisible otherwise, because no user is watching a response.
            CeleryIntegration(),
            # Log records become breadcrumbs, never events. Turning warnings into issues
            # is the "logging as error collection" mistake the book warns about, one level
            # up: the dashboard fills with expected conditions and real 500s get lost.
            LoggingIntegration(level=logging.INFO, event_level=None),
        ],
        # This app handles institutional email addresses and sample identifiers. Off means
        # no user record, no cookies, no request body attached to an event.
        send_default_pii=False,
        # ...and this catches the addresses that are inside the messages themselves.
        before_send=scrub_event,
        # Error monitoring only. Performance tracing is a separate decision with a separate
        # cost, and turning it on by accident is how a free tier disappears in a day.
        traces_sample_rate=0.0,
    )
