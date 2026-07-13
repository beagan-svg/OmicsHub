# OCS Database Viewer

A Django web application for viewing RNA-Seq sample data in the OCS (Open
Commercialized Sequencing) database and driving the alignment / post-QC /
ingest processing pipeline through the `ocs` CLI.

## Features

- **Sample browser** – filter and search samples by study set, organism,
  library prep method, vendor batch (RTX/MTX/ATX), and processing status.
- **Pipeline Checkout** – submit samples for alignment and post-QC, monitor
  running/completed/failed jobs, and manage the submission queue.
- **Per-user preferences** – column visibility, page size, and filter defaults.

## Project structure

```
config/                     Django project configuration
  settings/
    base.py                 Shared settings
    development.py           Local development (default)
    production.py            Production overrides (env-driven)
  urls.py                   Root URLs: admin, authentication, app include
  pipeline_config.yaml      Organism references, chemistries, workflow commands
ocs/                        The Django app (label: "ocs")
  models.py                 All database models
  views.py                  Sample browser (ProductionMainListView)
  queue_views.py            Queue API endpoints
  pipeline.py               Pipeline Checkout, job submission, pipeline API
  jobs.py                   Job monitor and queue-management views
  filters.py                django-filter definitions for the browser
  auth_views.py             Login, registration, profile, preferences
  adapters.py               Google SSO domain-restriction adapter
  pipeline_utils.py         OCS command building and job-status handling
  context_processors.py     Template helper functions
  middleware.py
  urls.py                   App URLs (namespace: "ocs")
  templatetags/             Template tags
  management/commands/      Data maintenance and diagnostic commands
  migrations/
templates/                  Project templates (base.html, registration/, ocs/)
static/                     Project static assets (ocs/css, ocs/js)
manage.py
```

## Requirements

- Python 3.10+
- PostgreSQL
- The `ocs` CLI (genomics-cloud-services), available on the server that runs
  the pipeline. Submission scripts source the gcs-cli virtualenv and set
  `AWS_PROFILE=aibs-bicore`.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # all views require login
```

The development settings (`config.settings.development`) are used by default
and connect to the local PostgreSQL database `prod_ocs` over a Unix socket.
Adjust the `DATABASES` block in `config/settings/development.py` if your local
setup differs.

## Running (development)

```bash
python manage.py runserver 0.0.0.0:8090
# or: make run
```

The app is at http://localhost:8090/. All pages require login; sign in with the
superuser you created.

### Toggling OCS command execution

`EXECUTE_OCS_COMMANDS` controls whether pipeline commands are actually run or
only logged to `pipeline_command_logs/`. Set it to `False` in
`development.py` to exercise the UI without submitting real jobs.

## Authentication

Every view requires an authenticated session (`LoginRequiredMixin` /
`@login_required`). Username/password login, registration, and password
management are built in under `/login/`, `/register/`, etc.

### Google SSO (django-allauth)

Google login is wired up but **off by default** (the app runs without it).
When enabled, hitting any login-required page redirects straight to Google,
auto-creates the account on first login, and grants full access. To enable it
in your deployment environment:

```bash
pip install django-allauth

# In Google Cloud Console, create an OAuth 2.0 Client ID (type: Web app) and
# add this authorized redirect URI:
#   https://<your-host>/accounts/google/login/callback/

export ENABLE_GOOGLE_SSO=true
export GOOGLE_CLIENT_ID='...'
export GOOGLE_CLIENT_SECRET='...'
export GOOGLE_SSO_ALLOWED_DOMAIN=        # empty = ANY Google account
                                         # e.g. "alleninstitute.org" to restrict
python manage.py migrate                 # creates allauth tables
```

> ⚠️ **Security:** with `GOOGLE_SSO_ALLOWED_DOMAIN` empty, *any* Google account
> on the internet can sign in and gets full access — including submitting and
> stopping pipeline jobs. For an internal tool, set it to your org domain
> (`alleninstitute.org`) and/or keep the app behind the institute network/VPN.
> Restricting later is just an env-var change; no code change.

## Production deployment

Production settings read all environment-specific values from the environment
and refuse to start if required ones are missing.

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
export SECRET_KEY='<random-50+-char-secret>'
export ALLOWED_HOSTS='ocs.example.org'
export CSRF_TRUSTED_ORIGINS='https://ocs.example.org'
export DB_NAME=prod_ocs DB_USER=svc_bicore DB_HOST=... DB_PASSWORD=...
# export USE_HTTPS=false   # only if TLS is terminated upstream without X-Forwarded-Proto

python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application
```

Static files are served by the front-end web server (e.g. nginx) or directly
by gunicorn from `staticfiles/` after `collectstatic`. When `USE_HTTPS` is true
(the default), secure cookies, HSTS, and SSL redirect are enabled.

## Useful Make targets

```bash
make run            # development server (PORT defaults to 8090)
make migrate        # apply migrations
make collectstatic  # collect static files
make test           # run tests
make clean          # remove __pycache__ / compiled files
```

## Logs

- Development: console output.
- Production: `logs/django.log` (rotating) plus console.
- Pipeline command audit trail: `pipeline_command_logs/`.
